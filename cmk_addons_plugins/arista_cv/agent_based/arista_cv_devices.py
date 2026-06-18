"""checkmk check plugin: Arista CVP device status (CVP-host view).

One service per device discovered in CVP inventory, all living on the CVP host.
Service name: "Arista CVP Device <hostname>"

Thresholds are configurable via the "Arista CVP Device Status" check
parameters rule (Setup > Services > Service monitoring rules).
"""

import json
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

DEFAULT_PARAMS: Dict[str, Any] = {
    "disconnected_state": int(State.CRIT),
    "compliance_warning_state": int(State.WARN),
    "compliance_error_state": int(State.CRIT),
    "streaming_inactive_state": int(State.WARN),
}


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

    # --- Connection ---
    conn_status = device.get("status", "Unknown")
    # CVP v2 API reports "Registered" for operational devices; older versions use "Connected"
    if conn_status in ("Connected", "Registered"):
        conn_state = State.OK
    else:
        conn_state = State(params.get("disconnected_state", DEFAULT_PARAMS["disconnected_state"]))

    hostname = device.get("hostname", "N/A")
    fqdn = device.get("fqdn", "") or hostname
    mac = device.get("systemMacAddress", "") or "N/A"

    yield Result(
        state=conn_state,
        summary=f"Connection: {conn_status.capitalize()}",
        details="\n".join([
            f"Hostname: {hostname}",
            f"FQDN: {fqdn}",
            f"IP: {device.get('ipAddress') or 'N/A'}",
            f"MAC: {mac}",
            f"Model: {device.get('modelName') or 'N/A'}",
            f"EOS: {device.get('version') or 'N/A'}",
            f"Serial: {device.get('serialNumber') or 'N/A'}",
            f"Container: {device.get('containerName') or 'N/A'}",
        ]),
    )

    # --- Compliance ---
    raw_compliance = device.get("complianceIndication") or "NONE"
    if raw_compliance == "NONE":
        compliance_state = State.OK
        compliance_label = "OK"
    elif raw_compliance == "WARNING":
        compliance_state = State(params.get("compliance_warning_state", DEFAULT_PARAMS["compliance_warning_state"]))
        compliance_label = "WARNING"
    else:
        compliance_state = State(params.get("compliance_error_state", DEFAULT_PARAMS["compliance_error_state"]))
        compliance_label = raw_compliance

    yield Result(state=compliance_state, summary=f"Compliance: {compliance_label}")

    # --- Streaming ---
    streaming = device.get("streamingStatus", "inactive")
    if streaming == "active":
        streaming_state = State.OK
    else:
        streaming_state = State(params.get("streaming_inactive_state", DEFAULT_PARAMS["streaming_inactive_state"]))

    yield Result(state=streaming_state, summary=f"Streaming: {streaming.capitalize()}")


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
