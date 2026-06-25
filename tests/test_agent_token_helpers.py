"""Tests for the pure token helpers in the special agent."""

import io

from conftest import make_jwt


# --- decode_token_expiry ----------------------------------------------------


def test_decode_token_expiry_valid(agent):
    token = make_jwt({"exp": 1750000000, "sub": "cvp-monitor"})
    result = agent.decode_token_expiry(token)
    assert result == {"decodable": True, "exp": 1750000000, "subject": "cvp-monitor"}


def test_decode_token_expiry_decodable_but_no_exp(agent):
    token = make_jwt({"sub": "cvp-monitor"})
    result = agent.decode_token_expiry(token)
    assert result["decodable"] is True
    assert result["exp"] is None
    assert result["subject"] == "cvp-monitor"


def test_decode_token_expiry_padding_needed(agent):
    # A payload whose base64 length is not a multiple of 4 without padding.
    token = make_jwt({"exp": 1, "sub": "a"})
    assert agent.decode_token_expiry(token)["exp"] == 1


def test_decode_token_expiry_not_three_segments(agent):
    result = agent.decode_token_expiry("only.two")
    assert result == {"decodable": False, "exp": None, "subject": ""}


def test_decode_token_expiry_bad_base64(agent):
    result = agent.decode_token_expiry("aaa.!!!notbase64!!!.sig")
    assert result["decodable"] is False


def test_decode_token_expiry_non_json_payload(agent):
    import base64

    payload = base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode()
    result = agent.decode_token_expiry(f"h.{payload}.s")
    assert result["decodable"] is False


def test_decode_token_expiry_alternate_subject_keys(agent):
    token = make_jwt({"exp": 5, "username": "svc-account"})
    assert agent.decode_token_expiry(token)["subject"] == "svc-account"


# --- normalize_valid_until --------------------------------------------------


def test_normalize_valid_until_epoch_int(agent):
    assert agent.normalize_valid_until(1750000000) == 1750000000


def test_normalize_valid_until_seconds_dict(agent):
    assert agent.normalize_valid_until({"seconds": 1750000000}) == 1750000000


def test_normalize_valid_until_rfc3339(agent):
    # 2025-01-01T00:00:00Z == 1735689600
    assert agent.normalize_valid_until("2025-01-01T00:00:00Z") == 1735689600


def test_normalize_valid_until_unset_is_none(agent):
    assert agent.normalize_valid_until(None) is None
    assert agent.normalize_valid_until(0) is None
    assert agent.normalize_valid_until("") is None
    assert agent.normalize_valid_until({"seconds": 0}) is None


def test_normalize_valid_until_garbage_is_none(agent):
    assert agent.normalize_valid_until("not-a-date") is None


# --- format_token_item ------------------------------------------------------


def test_format_token_item_user_and_description(agent):
    assert agent.format_token_item("svc-ansible", "ansible-prod", "id1") == (
        "svc-ansible / ansible-prod"
    )


def test_format_token_item_empty_description_uses_id(agent):
    assert agent.format_token_item("svc-ansible", "", "id1") == "svc-ansible / id1"


def test_format_token_item_empty_user_falls_back(agent):
    assert agent.format_token_item("", "ansible-prod", "id1") == "ansible-prod"
    assert agent.format_token_item("", "", "id1") == "id1"


# --- enumerate_service_tokens -----------------------------------------------


class _FakeApi:
    def __init__(self, tokens=None, exc=None):
        self._tokens = tokens or []
        self._exc = exc

    def svc_account_token_get_all(self):
        if self._exc:
            raise self._exc
        return self._tokens


class _FakeClient:
    def __init__(self, api):
        self.api = api


def test_enumerate_service_tokens_maps_fields(agent):
    client = _FakeClient(
        _FakeApi(
            tokens=[
                {
                    "id": "tok-1",
                    "description": "ansible",
                    "user": "svc-ansible",
                    "valid_until": 1750000000,
                    "last_used": 1749000000,
                }
            ]
        )
    )
    out = agent.enumerate_service_tokens(client)
    assert out == [
        {
            "id": "tok-1",
            "description": "ansible",
            "user": "svc-ansible",
            "valid_until": 1750000000,
            "last_used": 1749000000,
        }
    ]


def test_enumerate_service_tokens_error_returns_empty_and_warns(agent):
    client = _FakeClient(_FakeApi(exc=RuntimeError("permission denied")))
    err = io.StringIO()
    out = agent.enumerate_service_tokens(client, stderr=err)
    assert out == []
    assert "WARNING" in err.getvalue()
