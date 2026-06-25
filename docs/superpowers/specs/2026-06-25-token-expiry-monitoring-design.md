# Token Expiry Monitoring — Design

**Date:** 2026-06-25
**Status:** Approved (pending written-spec review)
**Component:** checkmk-arista-cv

## Problem

Arista CloudVision authentication for automation uses **service account tokens**.
These tokens expire. When a token expires the special agent silently stops
working — the next poll fails to connect and all CVP services go stale/UNKNOWN
with no advance warning.

We want proactive warning before a token expires:

- **WARN** when a token expires in **14 days or fewer**.
- **CRIT** when a token expires in **4 days or fewer** (including already expired).

## Goals

1. Warn ahead of expiry for the token the agent authenticates with.
2. Additionally monitor *all* service account tokens configured in the
   CVP/CVaaS instance (other automations, other admins), when permitted.
3. Surface this **only on the CVP/CVaaS host** — never on monitored device hosts.
4. Degrade gracefully: missing permissions, old CVP, or malformed tokens must
   never crash the agent or the existing checks.

## Non-goals

- Rotating / renewing / creating tokens (read-only monitoring only).
- Monitoring username/password credentials (they have no expiry to read).

## Background — how token expiry is known

Arista service account tokens are **JWTs** carrying an `exp` (expiry, epoch
seconds) claim in the base64url-encoded payload. The agent already holds its own
token, so it can decode `exp` locally with no extra API call. This works on any
CVP/CVaaS version and needs no special permissions.

To cover *other* tokens, CVP/CVaaS exposes the `arista.serviceaccount.v1`
Resource API, wrapped by cvprac (`svc_account_token_get_all()`), returning every
token with its expiry, owning account, and description.

- **Permissions:** enumeration requires the authenticating account to have read
  access to service accounts (typically admin). Least-privilege monitoring
  accounts will get a permission error.
- **Availability:** the Resource API requires CVaaS or CVP on-prem ~2021.x+.
  Older CVP lacks it.

The self-token JWT decode is therefore the robust **baseline**; the all-tokens
enumeration is an **add-on** that depends on permissions and version.

## Services

Both services live exclusively on the CVP/CVaaS host.

| Service | Item | Source | Availability |
|---|---|---|---|
| `Arista CVP Token` | none | JWT decode of the agent's own auth token | Whenever token auth is used |
| `Arista CVP Service Token <description>` | per token | Resource API `svc_account_token_get_all()` | Read perms + CVP ~2021.x+ / CVaaS |

When username/password auth is used, **no token sections are emitted**, so
neither service is discovered.

The agent's own token may also appear in the enumeration. This minor overlap is
**accepted and documented**: keeping a separate baseline service guarantees
coverage even when enumeration is unavailable. No cross-section de-duplication.

## Host scoping (critical constraint)

Token monitoring is a property of the CVP/CVaaS *instance*, not of individual
managed devices.

- Both `<<<arista_cv_token>>>` and `<<<arista_cv_service_tokens>>>` are emitted
  as **plain sections on the CVP host**, i.e. outside any `<<<<device>>>>`
  piggyback block.
- The `--piggyback` code path is **unchanged**: it still emits only
  `arista_cv_device_status` per device.
- Result: the two token services can only ever appear on the CVP/CVaaS host,
  regardless of whether piggyback mode is enabled.

## Components

### 1. Special agent — `agents/special/agent_arista_cv`

New pure helpers (importable for unit tests):

- `decode_token_expiry(token: str) -> dict`
  Splits the JWT on `.`, base64url-decodes the payload (with padding fix),
  parses JSON, extracts `exp` (int) and a subject (`sub`/`subject`/`username`
  if present). Returns:
  - `{"decodable": True, "exp": <int>, "subject": <str>}` on success
  - `{"decodable": True, "exp": None, "subject": <str>}` if decodable but no `exp`
  - `{"decodable": False, "exp": None, "subject": ""}` on any failure
    (not 3 parts, bad base64, bad JSON).
  Never raises.

- `normalize_valid_until(value) -> Optional[int]`
  Accepts whatever cvprac returns for a token's expiry (RFC3339 string, epoch
  int, `{"seconds": ...}` dict, or unset/zero) and returns epoch seconds, or
  `None` for non-expiring/unset. Never raises.

- `enumerate_service_tokens(client) -> List[dict]`
  Calls `client.api.svc_account_token_get_all()`, normalizes each entry to
  `{"id", "description", "user", "valid_until": <epoch|null>, "last_used"}`.
  On any exception (permission, missing method on old CVP, transport): writes a
  single `WARNING: ...` line to stderr and returns `[]`. Never raises.

Emission (only when a token is used for auth — CVP token auth or CVaaS):

```
<<<arista_cv_token:sep(0)>>>
{"decodable": true, "exp": 1750000000, "subject": "cvp-monitor"}
<<<arista_cv_service_tokens:sep(0)>>>
[{"id": "...", "description": "ansible", "user": "svc-ansible", "valid_until": 1755000000, "last_used": 1749000000}, ...]
```

Both are emitted on the CVP host, before/independent of any piggyback output.
`arista_cv_service_tokens` is emitted even when the list is empty (so the check
side is deterministic); an empty list simply discovers no per-token services.

### 2. Check plugin — `cmk_addons_plugins/arista_cv/agent_based/arista_cv_token.py`

Default params:

```python
DEFAULT_TOKEN_PARAMS = {"warn_days": 14, "crit_days": 4}
```

Shared helper:

- `check_token_expiry(exp: Optional[int], params, now: float) -> CheckResult`
  - `exp is None` → UNKNOWN, "token expiry not available" (self token undecodable
    / no `exp`).
  - else compute `days = (exp - now) / 86400`.
    - `days <= crit_days` (incl. negative/expired) → CRIT
    - `days <= warn_days` → WARN
    - else → OK
  - Summary: human expiry date (UTC) + days remaining (or "expired N days ago").
  - Yields a `Metric("token_expiry_days", days)`.

Two `AgentSection`s and two `CheckPlugin`s:

- `arista_cv_token`
  - parse → `dict | None`
  - discover → `Service()` if section present
  - check → if `not decodable` → UNKNOWN "token expiry not available";
    else `check_token_expiry(section["exp"], params, now)`.
  - `service_name="Arista CVP Token"`, `check_ruleset_name="arista_cv_token"`,
    `check_default_parameters=DEFAULT_TOKEN_PARAMS`.

- `arista_cv_service_tokens`
  - parse → `Dict[str, dict]` keyed by a stable item name (token `description`,
    falling back to `id`); skips entries without a usable key.
  - discover → one `Service(item=...)` per token.
  - check(item, params, section) →
    - item missing → UNKNOWN "token not found".
    - `valid_until is None` → OK, "non-expiring token" (legitimate state — *not*
      a decode failure, so not UNKNOWN).
    - else `check_token_expiry(valid_until, params, now)`.
    - details: owning account, last used (if present).
  - `service_name="Arista CVP Service Token %s"`,
    `check_ruleset_name="arista_cv_token"`,
    `check_default_parameters=DEFAULT_TOKEN_PARAMS`.

`now` comes from `time.time()` at check execution.

### 3. Ruleset — `cmk_addons_plugins/arista_cv/rulesets/check_params_arista_cv_token.py`

One `CheckParameters(name="arista_cv_token", topic=Topic.NETWORKING)` shared by
both check plugins (mirrors how `arista_cv_device_status` is shared today).

Form: a `Dictionary` with two `Integer` elements:

- `warn_days` — "Warn when expiring within (days)", default 14.
- `crit_days` — "Critical when expiring within (days)", default 4.

Condition: `HostAndItemCondition(item_title=Title("Token"))`, shared by both
plugins. This mirrors the existing `arista_cv_device_status` ruleset, which
already serves both an itemless plugin (`arista_cv_device_status`) and an
itemized one (`arista_cv_devices`) — confirming checkmk tolerates a mixed
itemless/itemized pair under one `HostAndItemCondition` ruleset. The itemless
self-token service matches the host part; the per-token services match per item.

### 4. Packaging — `build_mkp.py`

- Add to `files["cmk_addons_plugins"]`:
  - `arista_cv/agent_based/arista_cv_token.py`
  - `arista_cv/rulesets/check_params_arista_cv_token.py`
- Bump `version` (e.g. `1.0.5` → `1.1.0`).
- Extend `description` to mention token-expiry monitoring.

### 5. Documentation — `README.md`

- Under "What it monitors": add the two token services, the 14/4-day defaults,
  the ruleset, and the note that all-token enumeration needs admin read perms +
  CVP ~2021.x+/CVaaS and that token services live only on the CVP/CVaaS host.

## Error handling summary

| Situation | Behavior |
|---|---|
| Username/password auth | No token sections emitted; no token services |
| Self token not a decodable JWT / no `exp` | `decodable:false` or `exp:null` → `Arista CVP Token` = UNKNOWN |
| Enumeration: no permission / old CVP / API error | stderr WARNING, empty list → no per-token services; baseline unaffected |
| Enumerated token with no expiry set | per-token service = OK, "non-expiring" |
| Token expired | CRIT, "expired N days ago" |

## Testing

New `pytest` suite (repo has none today): `tests/test_arista_cv_token.py`.
The agent is a script without a `.py` extension; tests load it via
`importlib.util.spec_from_file_location` to import its helpers.

Cases:

- `decode_token_expiry`: valid token with `exp`; decodable but missing `exp`;
  malformed (not 3 segments); bad base64; non-JSON payload; padding-needed
  payload.
- `normalize_valid_until`: RFC3339 string; epoch int; `{"seconds": n}` dict;
  unset/zero/None.
- `check_token_expiry` boundaries: well in future (OK); exactly at/just under
  14 days (WARN); exactly at/just under 4 days (CRIT); expired/negative (CRIT);
  `exp=None` (UNKNOWN). Verify the `token_expiry_days` metric is emitted.
- Per-token check: `valid_until=None` → OK "non-expiring"; unknown item →
  UNKNOWN.

## Open questions

None.
