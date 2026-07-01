"""LicenseGuard tests: normalize/validate guards + full submit -> check consensus flow."""

A = "0xAAa0000000000000000000000000000000000001"
B = "0xBBb0000000000000000000000000000000000002"


# ------------------------------------------------------------------ unit: normalize
def test_normalize_check_default(contract):
    n = contract.normalize_check
    d = n({})
    assert d == {"conflict": False, "offending": [], "reasoning": "no reasoning"}
    assert d["conflict"] is False

def test_normalize_check_non_dict(contract):
    n = contract.normalize_check
    for bad in ("garbage", None, 123, ["x"], 3.5):
        d = n(bad)
        assert d["conflict"] is False
        assert d["offending"] == []
        assert d["reasoning"] == "no reasoning"

def test_normalize_check_offending_not_list(contract):
    n = contract.normalize_check
    assert n({"offending": "GPL-3.0"})["offending"] == []      # a bare string is not a list
    assert n({"offending": 42})["offending"] == []
    assert n({"offending": {"a": 1}})["offending"] == []
    # a real list is kept, coerced to non-empty strings only
    assert n({"offending": ["GPL-3.0", "MIT"]})["offending"] == ["GPL-3.0", "MIT"]
    assert n({"offending": ["GPL-3.0", 5, None, "  ", "AGPL-3.0"]})["offending"] == ["GPL-3.0", "AGPL-3.0"]

def test_normalize_check_conflict_truthy_coercion(contract):
    n = contract.normalize_check
    assert n({"conflict": True})["conflict"] is True
    assert n({"conflict": 1})["conflict"] is True
    assert n({"conflict": "yes"})["conflict"] is True
    assert n({"conflict": ["nonempty"]})["conflict"] is True
    assert n({"conflict": False})["conflict"] is False
    assert n({"conflict": 0})["conflict"] is False
    assert n({"conflict": ""})["conflict"] is False
    assert n({"conflict": None})["conflict"] is False

def test_normalize_check_reasoning(contract):
    n = contract.normalize_check
    assert n({"reasoning": "  "})["reasoning"] == "no reasoning"
    assert n({"reasoning": 99})["reasoning"] == "no reasoning"
    assert n({"reasoning": "GPL taints proprietary"})["reasoning"] == "GPL taints proprietary"
    assert len(n({"reasoning": "x" * 5000})["reasoning"]) == 600


# ------------------------------------------------------------------ unit: validate
def test_validate_check(contract):
    v = contract.validate_check
    assert v({"conflict": True, "offending": ["GPL-3.0"], "reasoning": "copyleft taints"})
    assert v({"conflict": False, "offending": [], "reasoning": "all permissive"})
    assert not v({"conflict": "true", "offending": [], "reasoning": "x"})    # conflict not a bool
    assert not v({"conflict": 1, "offending": [], "reasoning": "x"})         # 1 is not a real bool
    assert not v({"conflict": True, "offending": "GPL-3.0", "reasoning": "x"})  # offending not a list
    assert not v({"conflict": True, "offending": [1, 2], "reasoning": "x"})  # offending not strings
    assert not v({"conflict": True, "offending": [], "reasoning": "   "})    # empty reasoning
    assert not v("not a dict")


# ------------------------------------------------------------------ integration
def _new(contract):
    return contract, contract.LicenseGuard()

def test_full_flow(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    pid = c.submit_project("my-app", "Proprietary", ["MIT", "GPL-3.0", "Apache-2.0"])

    p = c.get_project(pid)
    assert p["exists"] is True
    assert p["state"] == "open"
    assert p["submitter"] == A
    assert p["dep_licenses"] == ["MIT", "GPL-3.0", "Apache-2.0"]
    assert p["conflict"] is False

    # consensus check — under the shim exec_prompt returns {} -> normalized default (conflict False)
    out = c.check(pid)
    assert isinstance(out["conflict"], bool)
    assert isinstance(out["offending"], list)
    assert out["conflict"] is False

    p2 = c.get_project(pid)
    assert p2["state"] == "checked"
    assert isinstance(p2["conflict"], bool)
    assert isinstance(p2["offending"], list)
    assert all(isinstance(x, str) for x in p2["offending"])

    # cannot re-check a checked project
    try:
        c.check(pid); assert False, "should not re-check"
    except Exception:
        pass

    st = c.stats()
    assert st["total_projects"] == 1
    assert st["checked"] == 1
    assert st["conflicts_found"] == 0
    mod.gl.message.sender_address = A

def test_check_unknown_project(contract):
    mod, c = _new(contract)
    try:
        c.check("999"); assert False, "unknown project must raise"
    except Exception:
        pass

def test_get_missing_project(contract):
    mod, c = _new(contract)
    assert c.get_project("404") == {"exists": False}

def test_submit_validation(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = B
    for args in [("", "MIT", ["MIT"]),          # empty name
                 ("app", "", ["MIT"]),          # empty license
                 ("app", "MIT", []),            # no deps
                 ("app", "MIT", ["   "]),       # deps all blank -> empty
                 ("app", "MIT", "MIT")]:        # deps not a list
        try:
            c.submit_project(*args); assert False, f"should reject {args}"
        except Exception:
            pass
    # a valid submit still works afterwards and dep strings are trimmed
    pid = c.submit_project("ok-app", "MIT", ["  MIT  ", "Apache-2.0"])
    assert c.get_project(pid)["dep_licenses"] == ["MIT", "Apache-2.0"]
    mod.gl.message.sender_address = B
