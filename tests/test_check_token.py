"""Tests for the arista_cv_token check plugin.

The pure policy (classify_expiry) needs no checkmk. The thin check wrappers are
exercised through the cmk stub installed by the `check` fixture.
"""

import json

DAY = 86400
NOW = 1_700_000_000  # fixed reference "now" for deterministic days math


# --- classify_expiry (pure policy) ------------------------------------------


def test_classify_far_future_is_ok(check):
    level, days = check.classify_expiry(NOW + 30 * DAY, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "ok"
    assert round(days) == 30


def test_classify_just_inside_warn_window(check):
    level, _ = check.classify_expiry(NOW + 14 * DAY, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "warn"


def test_classify_just_outside_warn_window_is_ok(check):
    level, _ = check.classify_expiry(NOW + 15 * DAY, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "ok"


def test_classify_just_inside_crit_window(check):
    level, _ = check.classify_expiry(NOW + 4 * DAY, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "crit"


def test_classify_expired_is_crit(check):
    level, days = check.classify_expiry(NOW - 2 * DAY, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "crit"
    assert days < 0


def test_classify_none_exp_is_unknown(check):
    level, days = check.classify_expiry(None, {"warn_days": 14, "crit_days": 4}, NOW)
    assert level == "unknown"
    assert days is None


# --- self-token check -------------------------------------------------------


def _states(results, State):
    return [r.state for r in results if isinstance(getattr(r, "state", None), State)]


def test_self_token_check_ok(check):
    State = check.State
    section = {"decodable": True, "exp": NOW + 30 * DAY, "subject": "cvp-monitor"}
    results = list(check._check_self_token(section, check.DEFAULT_TOKEN_PARAMS, now=NOW))
    assert State.OK in _states(results, State)


def test_self_token_check_warn(check):
    State = check.State
    section = {"decodable": True, "exp": NOW + 10 * DAY, "subject": "cvp-monitor"}
    results = list(check._check_self_token(section, check.DEFAULT_TOKEN_PARAMS, now=NOW))
    assert State.WARN in _states(results, State)


def test_self_token_check_undecodable_is_unknown(check):
    State = check.State
    section = {"decodable": False, "exp": None, "subject": ""}
    results = list(check._check_self_token(section, check.DEFAULT_TOKEN_PARAMS, now=NOW))
    assert State.UNKNOWN in _states(results, State)


def test_self_token_check_emits_metric(check):
    section = {"decodable": True, "exp": NOW + 30 * DAY, "subject": "x"}
    results = list(check._check_self_token(section, check.DEFAULT_TOKEN_PARAMS, now=NOW))
    metrics = [r for r in results if isinstance(r, check.Metric)]
    assert any(m.name == "token_expiry_days" for m in metrics)


# --- per-token check --------------------------------------------------------


def test_service_token_non_expiring_is_ok(check):
    State = check.State
    section = {"svc / t": {"id": "i", "description": "t", "user": "svc", "valid_until": None}}
    results = list(
        check._check_service_token("svc / t", check.DEFAULT_TOKEN_PARAMS, section, now=NOW)
    )
    assert State.OK in _states(results, State)
    assert any("non-expiring" in getattr(r, "summary", "").lower() for r in results)


def test_service_token_unknown_item(check):
    State = check.State
    results = list(check._check_service_token("missing", check.DEFAULT_TOKEN_PARAMS, {}, now=NOW))
    assert State.UNKNOWN in _states(results, State)


def test_service_token_crit_when_expiring_soon(check):
    State = check.State
    section = {
        "svc / t": {"id": "i", "description": "t", "user": "svc", "valid_until": NOW + 2 * DAY}
    }
    results = list(
        check._check_service_token("svc / t", check.DEFAULT_TOKEN_PARAMS, section, now=NOW)
    )
    assert State.CRIT in _states(results, State)


# --- parse / discovery ------------------------------------------------------


def test_parse_self_token(check):
    raw = {"decodable": True, "exp": 1, "subject": "x"}
    section = check.parse_arista_cv_token([[json.dumps(raw)]])
    assert section == raw


def test_parse_service_tokens_keys_by_item(check):
    raw = [
        {"id": "i1", "description": "ansible", "user": "svc-a", "valid_until": 1},
        {"id": "i2", "description": "terraform", "user": "svc-b", "valid_until": 2},
    ]
    section = check.parse_arista_cv_service_tokens([[json.dumps(raw)]])
    assert set(section.keys()) == {"svc-a / ansible", "svc-b / terraform"}


def test_parse_service_tokens_disambiguates_duplicates(check):
    raw = [
        {"id": "i1", "description": "ansible", "user": "svc-a", "valid_until": 1},
        {"id": "i2", "description": "ansible", "user": "svc-a", "valid_until": 2},
    ]
    section = check.parse_arista_cv_service_tokens([[json.dumps(raw)]])
    assert len(section) == 2
    assert any("(i2)" in k for k in section)


def test_discover_service_tokens_one_per_item(check):
    section = {
        "svc-a / ansible": {"id": "i1"},
        "svc-b / terraform": {"id": "i2"},
    }
    services = list(check.discover_arista_cv_service_tokens(section))
    assert {s.item for s in services} == {"svc-a / ansible", "svc-b / terraform"}
