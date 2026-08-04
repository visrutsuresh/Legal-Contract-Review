"""The tamper-evident audit chain. Pure functions, no I/O, highest value per line:
if this breaks silently the whole "we can prove what the pipeline did" claim goes."""

import hashlib

from app.audit import GENESIS, chain, chain_as, verify


def test_chain_links_first_entry_to_genesis():
    log = chain([], ["intake done"])
    assert len(log) == 1
    assert log[0]["prev"] == GENESIS
    assert verify(log) == -1


def test_chain_links_across_multiple_appends():
    # the reducer is called once per node, so continuity ACROSS calls is the
    # property that matters, not continuity within one call
    log = chain([], ["a", "b"])
    log = chain(log, ["c"])
    assert [e["step"] for e in log] == ["a", "b", "c"]
    for i, entry in enumerate(log):
        assert entry["prev"] == (GENESIS if i == 0 else log[i - 1]["hash"])
    assert verify(log) == -1


def test_chain_does_not_mutate_the_existing_log():
    # LangGraph reducers must be pure: the old list is still live elsewhere
    existing = chain([], ["a"])
    before = list(existing)
    chain(existing, ["b"])
    assert existing == before


def test_verify_returns_minus_one_on_an_intact_log():
    assert verify(chain([], ["a", "b", "c"])) == -1
    assert verify([]) == -1  # an empty log is trivially intact


def test_verify_points_at_the_mutated_entry():
    log = chain([], ["a", "b", "c"])
    log[1]["step"] = "b, but edited later"
    # entry 1's stored hash no longer matches its step, and that is the FIRST
    # place the recomputation diverges, so the index must be 1 and not 2
    assert verify(log) == 1


def test_verify_catches_a_deleted_entry():
    log = chain([], ["a", "b", "c"])
    del log[1]
    # what was entry 2 now sits at index 1 and its prev points at a hash that
    # is no longer above it
    assert verify(log) == 1


def test_chain_as_records_the_acting_human():
    log = chain_as([], ["decision accepted: clause 5"], by="priya@papyrus.dev")
    assert log[0]["by"] == "priya@papyrus.dev"
    assert verify(log) == -1


def test_forged_actor_detected():
    # the whole point of hashing `by`: you cannot reattribute someone else's
    # sign-off to yourself after the fact
    log = chain_as([], ["decision accepted: clause 5"], by="priya@papyrus.dev")
    log[0]["by"] = "theo@papyrus.dev"
    assert verify(log) == 0


def test_forged_timestamp_detected():
    log = chain_as([], ["decision accepted: clause 5"], by="priya@papyrus.dev")
    log[0]["ts"] = "2020-01-01T00:00:00+00:00"
    assert verify(log) == 0


def test_legacy_step_only_entries_still_verify():
    # contracts reviewed before ts/by landed carry entries with neither field.
    # they must keep verifying, or every existing audit trail reads as tampered.
    # built with the OLD formula on purpose: sha256("prev|step"), no ts, no by
    old_hash = hashlib.sha256(f"{GENESIS}|intake done".encode()).hexdigest()
    legacy = [{"step": "intake done", "prev": GENESIS, "hash": old_hash}]
    assert verify(legacy) == -1
    # and a new entry can be appended on top of the old chain without breaking it
    grown = chain_as(legacy, ["decision accepted: clause 3"], by="priya@papyrus.dev")
    assert verify(grown) == -1
