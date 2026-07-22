"""The react loop. router.think is monkeypatched with a scripted sequence of
replies so no test here ever touches the GPU lane; run_tool is stubbed too, so
what is under test is purely the loop's control flow."""

import json

import pytest

from app import router, tools
from app.agents_base import MAX_STEPS, _parse, react


class Script:
    """Hands back canned model replies in order and keeps the prompts it saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt, max_new_tokens=1024):
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError("react asked for more replies than the script has")
        return json.dumps(self.replies.pop(0))


@pytest.fixture
def lane(monkeypatch):
    """Install a script and a tool stub; returns a function to arm them."""
    calls = []
    monkeypatch.setattr(tools, "run_tool", lambda name, args: calls.append((name, args)) or f"result of {name}")

    def arm(replies):
        script = Script(replies)
        monkeypatch.setattr(router, "think", script)
        script.calls = calls
        return script

    return arm


FETCH = {"thought": "need the standard", "action": "template_fetch", "args": {"contract_type": "nda"}}


def test_tool_call_then_finish(lane):
    script = lane([FETCH, {"thought": "done", "action": "finish", "result": {"findings": [{"clause_id": "c01"}]}}])
    out = react("SYSTEM", "CONTEXT", ["template_fetch"])
    assert out == {"findings": [{"clause_id": "c01"}]}
    assert script.calls == [("template_fetch", {"contract_type": "nda"})]
    assert len(script.prompts) == 2


def test_transcript_carries_the_observation(lane):
    script = lane([FETCH, {"action": "finish", "result": {}}])
    react("SYSTEM", "CONTEXT", ["template_fetch"])
    assert "result of template_fetch" in script.prompts[1]
    assert "CONTEXT" in script.prompts[1]


def test_finish_with_no_result_key_returns_empty_dict(lane):
    lane([{"action": "finish"}])
    assert react("SYSTEM", "CONTEXT", ["template_fetch"]) == {}


def test_a_tool_outside_the_allowed_list_is_refused(lane):
    script = lane([
        {"action": "rules_read", "args": {"contract_type": "nda"}},  # not allowed for this agent
        {"action": "finish", "result": {"ok": True}},
    ])
    out = react("SYSTEM", "CONTEXT", ["template_fetch"])
    assert out == {"ok": True}
    assert script.calls == []  # never dialled
    assert "unknown action 'rules_read'" in script.prompts[1]


def test_a_repeated_tool_call_is_blocked_and_counted(lane):
    # same tool AND same args three times: the first runs, the next two are
    # refused and bump `redundant`. At 2 the loop stops asking nicely and
    # forces a decision.
    script = lane([FETCH, FETCH, FETCH, {"action": "finish", "result": {"findings": []}}])
    out = react("SYSTEM", "CONTEXT", ["template_fetch"])
    assert out == {"findings": []}
    assert script.calls == [("template_fetch", {"contract_type": "nda"})]  # ran ONCE
    assert "already called" in script.prompts[2]
    assert "STOP calling tools" in script.prompts[3]  # redundant hit 2
    assert "STOP calling tools" not in script.prompts[2]


def test_same_tool_with_different_args_is_not_redundant(lane):
    script = lane([
        {"action": "precedent_search", "args": {"query": "liability cap"}},
        {"action": "precedent_search", "args": {"query": "indemnity"}},
        {"action": "finish", "result": {}},
    ])
    react("SYSTEM", "CONTEXT", ["precedent_search"])
    assert len(script.calls) == 2


def test_arg_ordering_does_not_defeat_the_duplicate_guard(lane):
    # the cache key is sorted JSON, so a reordered args dict is still a repeat
    script = lane([
        {"action": "precedent_search", "args": {"a": 1, "b": 2}},
        {"action": "precedent_search", "args": {"b": 2, "a": 1}},
        {"action": "finish", "result": {}},
    ])
    react("SYSTEM", "CONTEXT", ["precedent_search"])
    assert len(script.calls) == 1


def test_the_last_step_is_always_told_to_finish(lane):
    script = lane([FETCH, {"action": "finish", "result": {}}])
    react("SYSTEM", "CONTEXT", ["template_fetch"], max_steps=2)
    assert "STOP calling tools" not in script.prompts[0]
    assert "STOP calling tools" in script.prompts[1]


def test_hitting_the_step_cap_raises_timeout(lane):
    # a model that never finishes must not loop forever; guarded() upstream
    # turns this into one retry then a degraded inspector report
    calls = [
        {"action": "precedent_search", "args": {"query": f"q{i}"}}
        for i in range(MAX_STEPS)
    ]
    script = lane(calls)
    with pytest.raises(TimeoutError, match="step cap"):
        react("SYSTEM", "CONTEXT", ["precedent_search"])
    assert len(script.prompts) == MAX_STEPS


def test_max_steps_is_honoured(lane):
    script = lane([{"action": "precedent_search", "args": {"query": f"q{i}"}} for i in range(3)])
    with pytest.raises(TimeoutError):
        react("SYSTEM", "CONTEXT", ["precedent_search"], max_steps=3)
    assert len(script.prompts) == 3


def test_unparseable_reply_propagates(monkeypatch):
    # _parse raising ValueError is the signal callers (extraction_agent) retry on
    monkeypatch.setattr(router, "think", lambda prompt, max_new_tokens=1024: "prose, not JSON")
    with pytest.raises(ValueError):
        react("SYSTEM", "CONTEXT", ["template_fetch"])


# --- _parse -----------------------------------------------------------------


def test_parse_digs_the_object_out_of_surrounding_chatter():
    raw = 'Sure! Here is my answer:\n{"action": "finish", "result": {"findings": []}}\nHope that helps.'
    assert _parse(raw) == {"action": "finish", "result": {"findings": []}}


def test_parse_takes_the_outermost_braces():
    assert _parse('{"a": {"b": 1}}') == {"a": {"b": 1}}


def test_parse_raises_on_prose():
    with pytest.raises(ValueError):
        _parse("no json here at all")
