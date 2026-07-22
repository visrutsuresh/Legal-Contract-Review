"""The tamper-evident audit chain. Pure functions, no I/O, highest value per line:
if this breaks silently the whole "we can prove what the pipeline did" claim goes."""

from app.audit import GENESIS, _hash, chain, verify


def test_chain_links_first_entry_to_genesis():
    log = chain([], ["intake done"])
    assert len(log) == 1
    assert log[0]["prev"] == GENESIS
    assert log[0]["hash"] == _hash(GENESIS, "intake done")


def test_chain_links_across_multiple_appends():
    # the reducer is called once per node, so continuity ACROSS calls is the
    # property that matters, not continuity within one call
    log = chain([], ["a", "b"])
    log = chain(log, ["c"])
    assert [e["step"] for e in log] == ["a", "b", "c"]
    for i, entry in enumerate(log):
        expected_prev = GENESIS if i == 0 else log[i - 1]["hash"]
        assert entry["prev"] == expected_prev
        assert entry["hash"] == _hash(expected_prev, str(entry["step"]))


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
