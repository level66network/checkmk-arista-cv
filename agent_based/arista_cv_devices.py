"""checkmk check plugin: Arista CVP device status (CVP-host view).

One service per device discovered in CVP inventory, all living on the CVP host.
Service name: "Arista CVP Device <hostname>"

All thresholds are configurable via the "Arista CVP Device Status" check
parameters rule (Setup > Services > Service monitoring rules).
"""

import json
import time
from typing import Any, Dict, Mapping, Optional

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    StringTable,
)

Device = Dict[str, Any]
Section = Dict[str, Device]  # keyed by hostname

# Default thresholds — overridden by WATO check parameters rule.
# last_contact_levels: (warn_seconds, crit_seconds)
DEFAULT_PARAMS: Dict[str, Any] = {
    "disconnected_state": int(State.CRIT),
    "streaming_inactive_state": int(State.WARN),
    "compliance_warning_state": int(State.WARN),
    "compliance_error_state": int(State.CRIT),
    "pending_tasks_state": int(State.WARN),
    "last_contact_levels": (600, 1800),   # 10 min warn, 30 min crit
}


def _format_age(seconds: float) -> str:
    """Return a human-readable duration string, e.g. '2h 15m'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def parse_arista_cv_devices(string_table: StringTable) -> Section:
    if not string_table:
        return {}

    try:
        raw = json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError, KeyError):
        return {}

    if not isinstance(raw, list):
        return {}

    section: Section = {}
    for device in raw:
        if not isinstance(device, dict):
            continue
        hostname = device.get("hostname", "")
        if hostname:
            section[hostname] = device

    return section


def check_device(device: Device, params: Mapping[str, Any]) -> CheckResult:
    """Shared check logic used by both the CVP-host and piggyback check plugins."""

    # --- Connection status ---
    conn_status = device.get("status", "Unknown")
    if conn_status == "Connected":
        conn_state = State.OK
    else:
        conn_state = State(
            params.get("disconnected_state", DEFAULT_PARAMS["disconnected_state"])
        )

    hostname = device.get("hostname", "N/A")
    fqdn = device.get("fqdn", "") or hostname
    mac = device.get("systemMacAddress", "") or "N/A"

    yield Result(
        state=conn_state,
        summary=f"Connection: {conn_status}",
        details=(
            f"Hostname: {hostname} | FQDN: {fqdn} | "
            f"IP: {device.get('ipAddress') or 'N/A'} | "
            f"MAC: {mac} | "
            f"Model: {device.get('modelName') or 'N/A'} | "
            f"EOS: {device.get('version') or 'N/A'} | "
            f"Serial: {device.get('serialNumber') or 'N/A'} | "
            f"Container: {device.get('containerName') or 'N/A'}"
        ),
    )

    # --- Compliance ---
    compliance = device.get("complianceIndication", "NONE")
    if compliance == "NONE":
        compliance_state = State.OK
    elif compliance == "WARNING":
        compliance_state = State(
            params.get("compliance_warning_state", DEFAULT_PARAMS["compliance_warning_state"])
        )
    else:
        # ERROR or any unrecognised value
        compliance_state = State(
            params.get("compliance_error_state", DEFAULT_PARAMS["compliance_error_state"])
        )

    yield Result(state=compliance_state, summary=f"Compliance: {compliance}")

    # --- Streaming telemetry ---
    streaming = device.get("streamingStatus", "inactive")
    if streaming == "active":
        streaming_state = State.OK
    else:
        streaming_state = State(
            params.get("streaming_inactive_state", DEFAULT_PARAMS["streaming_inactive_state"])
        )

    yield Result(state=streaming_state, summary=f"Streaming: {streaming}")

    # --- Pending tasks ---
    task_count: int = device.get("taskCount", 0)
    if task_count > 0:
        task_state = State(
            params.get("pending_tasks_state", DEFAULT_PARAMS["pending_tasks_state"])
        )
        yield Result(state=task_state, summary=f"Pending tasks: {task_count}")
    else:
        yield Result(state=State.OK, summary="Pending tasks: 0")

    # --- Last contact ---
    last_sync_raw = device.get("lastSyncUp")
    if not last_sync_raw:
        yield Result(state=State.UNKNOWN, summary="Last contact: unknown")
        return

    # CVP uses millisecond epoch timestamps; normalise to seconds
    last_sync_s = (last_sync_raw / 1000.0) if last_sync_raw > 1e10 else float(last_sync_raw)
    age_s = time.time() - last_sync_s

    warn_s, crit_s = params.get("last_contact_levels", DEFAULT_PARAMS["last_contact_levels"])

    if age_s >= crit_s:
        contact_state = State.CRIT
    elif age_s >= warn_s:
        contact_state = State.WARN
    else:
        contact_state = State.OK

    yield Result(
        state=contact_state,
        summary=f"Last contact: {_format_age(age_s)} ago",
    )


def discover_arista_cv_devices(section: Section) -> DiscoveryResult:
    for hostname in section:
        yield Service(item=hostname)


def check_arista_cv_devices(
    item: str, params: Mapping[str, Any], section: Section
) -> CheckResult:
    device: Optional[Device] = section.get(item)
    if device is None:
        yield Result(state=State.UNKNOWN, summary="Device not found in CVP inventory")
        return
    yield from check_device(device, params)


agent_section_arista_cv_devices = AgentSection(
    name="arista_cv_devices",
    parse_function=parse_arista_cv_devices,
)

check_plugin_arista_cv_devices = CheckPlugin(
    name="arista_cv_devices",
    service_name="Arista CVP Device %s",
    discovery_function=discover_arista_cv_devices,
    check_function=check_arista_cv_devices,
    check_ruleset_name="arista_cv_device_status",
    check_default_parameters=DEFAULT_PARAMS,
)
