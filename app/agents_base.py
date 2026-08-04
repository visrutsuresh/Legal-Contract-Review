import json

from app import router, tools

MAX_STEPS = 6


_PY_LITERALS = {"True": "true", "False": "false", "None": "null"}


def _jsonify_python_literals(s: str) -> str:
    # Rewrite bare True/False/None that sit OUTSIDE strings. Anything inside
    # quotes is copied untouched, so a finding whose text merely mentions the
    # word True is never corrupted.
    out: list[str] = []
    i, in_str, esc = 0, False, False
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        for word, repl in _PY_LITERALS.items():
            after = s[i + len(word) : i + len(word) + 1]
            before = s[i - 1 : i]
            if s.startswith(word, i) and not (after.isalnum() or after == "_") and not (before.isalnum() or before == "_"):
                out.append(repl)  # word boundaries checked, so TrueValue survives intact
                i += len(word)
                break
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse(raw: str) -> dict:
    # the model sometimes emits a second JSON object or prose after its answer;
    # take the first complete object instead of slicing to the last brace
    body = raw[raw.find("{") :]
    try:
        obj, _ = json.JSONDecoder().raw_decode(body)
        return obj
    except json.JSONDecodeError:
        # The AWQ checkpoint sometimes writes Python literals inside otherwise
        # perfectly good JSON ("required": True). Strict JSON then rejects the
        # WHOLE reply: a 7kB template-inspector answer full of real findings was
        # being binned over one capital letter, and temperature 0 meant the retry
        # reproduced it exactly, so the inspector reported nothing. Measured
        # 2026-07-29; this is the likeliest cause of the kestrel recall dip that
        # was nearly blamed on AWQ quality.
        obj, _ = json.JSONDecoder().raw_decode(_jsonify_python_literals(body))
        return obj


def react(
    system: str,
    context: str,
    allowed_tools: list[str],
    max_steps: int = MAX_STEPS,
    max_new_tokens: int = 4096,
) -> dict:
    """Reason -> act -> observe loop. Returns the agent's finish result dict.
    Blocks repeated tool call and forces a decision near the cap ( #1 lessons).

    max_new_tokens is PER AGENT. 4096 was chosen so an inspector's multi-finding
    JSON could not truncate mid-string, then got charged to every agent including
    ones whose whole answer is a sentence. Callers pass their size from
    agents.TOKENS."""
    transcript, cache, redundant = "", {}, 0
    for step in range(max_steps):
        must_finish = redundant >= 2 or step >= max_steps - 1
        # the second sentence matters: small models spot issues in mid-loop thoughts
        # and then forget them at finish time unless told to carry them over
        hint = "\nSTOP calling tools. Reply ONLY with the finish JSON. Include every issue you already identified in your thoughts above as findings." if must_finish else ""
        move = _parse(router.think(f"{system}\n\n{context}\n{transcript}{hint}\nYour JSON:", max_new_tokens=max_new_tokens))
        action = move.get("action")
        if action == "finish":
            return move.get("result", {})
        if action not in allowed_tools:
            # name the real options: a lost model otherwise invents the same tool forever
            transcript += f"\nunknown action {action!r}; your only actions are {allowed_tools} or finish"
            continue
        args = move.get("args", {}) or {}
        key = f"{action}:{json.dumps(args, sort_keys=True)}"
        if key in cache:
            redundant += 1
            transcript += f"\n{action} already called; its result is above. Do not repeat it."
            continue
        obs = tools.run_tool(action, args)
        cache[key] = obs
        transcript += f"\n{action}({args}) -> {obs}"
    raise TimeoutError("agent hit the step cap without finishing")
