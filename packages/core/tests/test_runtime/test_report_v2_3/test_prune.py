from openlia.llm.runtime.report_v2_3.research import prune_empty


def test_drops_none_empty_string_and_empty_containers():
    payload = {
        "keep": "value",
        "null": None,
        "blank": "",
        "empty_list": [],
        "empty_dict": {},
    }
    assert prune_empty(payload) == {"keep": "value"}


def test_keeps_zero_false_and_zero_float():
    payload = {"margin": 0.0, "count": 0, "flag": False, "zero_str": "0"}
    # None of these are empty — a zero margin or false flag is real data.
    assert prune_empty(payload) == payload


def test_recurses_and_drops_parents_that_become_empty():
    payload = {
        "income": {"revenue": 100, "tax": None, "notes": ""},
        "balance": {"goodwill": None, "intangibles": ""},
    }
    # ``balance`` loses every child, so it is dropped entirely.
    assert prune_empty(payload) == {"income": {"revenue": 100}}


def test_preserves_list_length_and_prunes_elements():
    payload = {
        "quarters": [
            {"rev": 10, "missing": None},
            {"rev": 20, "missing": ""},
            {"rev": 30},
        ]
    }
    pruned = prune_empty(payload)
    assert pruned == {"quarters": [{"rev": 10}, {"rev": 20}, {"rev": 30}]}
    # Length is never changed — positional/counted arrays stay intact.
    assert len(pruned["quarters"]) == 3


def test_preserves_dict_key_order():
    payload = {"a": 1, "drop": None, "b": 2, "c": 3}
    assert list(prune_empty(payload).keys()) == ["a", "b", "c"]


def test_scalars_and_non_container_top_level_returned_unchanged():
    assert prune_empty("text") == "text"
    assert prune_empty(42) == 42
    assert prune_empty(None) is None


def test_empty_list_at_top_level_is_returned_as_empty_list():
    # A list value is only dropped when it is a dict key's value; on its
    # own it is preserved (callers rely on this for meaningful "[]").
    assert prune_empty([]) == []
