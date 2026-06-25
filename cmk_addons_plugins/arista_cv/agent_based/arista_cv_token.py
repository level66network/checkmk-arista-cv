"""checkmk check plugin: Arista CVP / CVaaS service account token expiry.

Two services, both living on the CVP/CVaaS host (never pushed to device hosts):

  - "Arista CVP Token"                 the token the special agent itself uses,
                                       read by decoding the JWT exp claim.
  - "Arista CVP Service Token <user> / <description>"
                                       one per service account token enumerated
                                       via the CVP Resource API.

Both warn ahead of expiry. Thresholds are configurable via the "Arista CVP
Token" check parameters rule (default: WARN 14 days, CRIT 4 days).
"""

import json
import time
from typing import Any, Dict, Mapping, Optional, Tuple

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)

SelfSection = Dict[str, Any]
ServiceTokens = Dict[str, Dict[str, Any]]

DAY = 86400

DEFAULT_TOKEN_PARAMS: Dict[str, int] = {"warn_days": 14, "crit_days": 4}


# --- pure policy ------------------------------------------------------------


def classify_expiry(
    exp: Optional[int], params: Mapping[str, Any], now: float
) -> Tuple[str, Optional[float]]:
    """Classify a token expiry into a level and the days remaining.

    Returns ("ok"|"warn"|"crit"|"unknown", days). days is None only when exp is
    unknown. A negative days value means the token already expired (crit).
    """
    if exp is None:
        return "unknown", None

    warn_days = params.get("warn_days", DEFAULT_TOKEN_PARAMS["warn_days"])
    crit_days = params.get("crit_days", DEFAULT_TOKEN_PARAMS["crit_days"])

    days = (exp - now) / DAY
    if days <= crit_days:
        return "crit", days
    if days <= warn_days:
        return "warn", days
    return "ok", days


_LEVEL_STATE = {
    "ok": State.OK,
    "warn": State.WARN,
    "crit": State.CRIT,
    "unknown": State.UNKNOWN,
}


def _expiry_results(
    exp: Optional[int], params: Mapping[str, Any], now: float, label: str
) -> CheckResult:
    """Yield the Result + Metric for a single token's expiry."""
    level, days = classify_expiry(exp, params, now)
    state = _LEVEL_STATE[level]

    if exp is None:
        yield Result(state=state, summary=f"{label}: expiry not available")
        return

    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exp))
    if days is not None and days < 0:
        summary = f"{label}: expired {abs(round(days))} days ago ({when})"
    else:
        summary = f"{label}: expires in {round(days)} days ({when})"

    yield Result(state=state, summary=summary)
    yield Metric("token_expiry_days", days if days is not None else 0.0)


# --- self token -------------------------------------------------------------


def parse_arista_cv_token(string_table: StringTable) -> Optional[SelfSection]:
    if not string_table:
        return None
    try:
        data = json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError, KeyError):
        return None
    return data if isinstance(data, dict) else None


def discover_arista_cv_token(section: Optional[SelfSection]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def _check_self_token(
    section: SelfSection, params: Mapping[str, Any], now: float
) -> CheckResult:
    subject = section.get("subject") or "service account token"
    if not section.get("decodable", False) or section.get("exp") is None:
        yield Result(
            state=State.UNKNOWN,
            summary=f"{subject}: token expiry not available",
        )
        return
    yield from _expiry_results(section.get("exp"), params, now, subject)


def check_arista_cv_token(
    params: Mapping[str, Any], section: Optional[SelfSection]
) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No token data available")
        return
    yield from _check_self_token(section, params, time.time())


# --- enumerated service account tokens --------------------------------------


def _item_for(token: Dict[str, Any]) -> str:
    user = str(token.get("user") or "").strip()
    description = str(token.get("description") or "").strip()
    token_id = str(token.get("id") or "").strip()
    if user:
        return f"{user} / {description}" if description else f"{user} / {token_id}"
    return description or token_id


def parse_arista_cv_service_tokens(string_table: StringTable) -> ServiceTokens:
    if not string_table:
        return {}
    try:
        raw = json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError, KeyError):
        return {}
    if not isinstance(raw, list):
        return {}

    section: ServiceTokens = {}
    for token in raw:
        if not isinstance(token, dict):
            continue
        item = _item_for(token)
        if not item:
            continue
        if item in section:
            # Disambiguate collisions so every token keeps a distinct service.
            item = f"{item} ({token.get('id', '')})"
        section[item] = token
    return section


def discover_arista_cv_service_tokens(section: ServiceTokens) -> DiscoveryResult:
    for item in section:
        yield Service(item=item)


def _check_service_token(
    item: str, params: Mapping[str, Any], section: ServiceTokens, now: float
) -> CheckResult:
    token = section.get(item)
    if token is None:
        yield Result(state=State.UNKNOWN, summary="Token not found in CVP inventory")
        return

    valid_until = token.get("valid_until")
    if valid_until is None:
        yield Result(state=State.OK, summary="Non-expiring token")
    else:
        yield from _expiry_results(valid_until, params, now, "Token")

    details = []
    if token.get("user"):
        details.append(f"Account: {token['user']}")
    if token.get("description"):
        details.append(f"Description: {token['description']}")
    if token.get("id"):
        details.append(f"Token ID: {token['id']}")
    if token.get("last_used"):
        details.append(
            "Last used: "
            + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(token["last_used"]))
        )
    if details:
        yield Result(state=State.OK, notice="\n".join(details))


def check_arista_cv_service_tokens(
    item: str, params: Mapping[str, Any], section: ServiceTokens
) -> CheckResult:
    yield from _check_service_token(item, params, section, time.time())


# --- registration -----------------------------------------------------------

agent_section_arista_cv_token = AgentSection(
    name="arista_cv_token",
    parse_function=parse_arista_cv_token,
)

check_plugin_arista_cv_token = CheckPlugin(
    name="arista_cv_token",
    service_name="Arista CVP Token",
    discovery_function=discover_arista_cv_token,
    check_function=check_arista_cv_token,
    check_ruleset_name="arista_cv_token",
    check_default_parameters=DEFAULT_TOKEN_PARAMS,
)

agent_section_arista_cv_service_tokens = AgentSection(
    name="arista_cv_service_tokens",
    parse_function=parse_arista_cv_service_tokens,
)

check_plugin_arista_cv_service_tokens = CheckPlugin(
    name="arista_cv_service_tokens",
    service_name="Arista CVP Service Token %s",
    discovery_function=discover_arista_cv_service_tokens,
    check_function=check_arista_cv_service_tokens,
    check_ruleset_name="arista_cv_token",
    check_default_parameters=DEFAULT_TOKEN_PARAMS,
)
