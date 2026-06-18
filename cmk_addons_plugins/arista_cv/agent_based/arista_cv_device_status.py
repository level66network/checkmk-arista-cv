"""checkmk check plugin: Arista CVP device status (piggyback / per-device host).

Receives data via the piggyback mechanism: the special agent emits
  <<<<hostname>>>>
  <<<arista_cv_device_status:sep(0)>>>
  {...}
  <<<<>>>>
for every device. checkmk routes these sections to the matching host, giving
each network device its own "Arista CVP Status" service.

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

from .arista_cv_devices import DEFAULT_PARAMS, check_device

Device = Dict[str, Any]


def parse_arista_cv_device_status(string_table: StringTable) -> Optional[Device]:
    if not string_table:
        return None

    try:
        data = json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError, KeyError):
        return None

    return data if isinstance(data, dict) else None


def discover_arista_cv_device_status(section: Optional[Device]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def check_arista_cv_device_status(
    params: Mapping[str, Any], section: Optional[Device]
) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No CVP device data available")
        return
    yield from check_device(section, params)


agent_section_arista_cv_device_status = AgentSection(
    name="arista_cv_device_status",
    parse_function=parse_arista_cv_device_status,
)

check_plugin_arista_cv_device_status = CheckPlugin(
    name="arista_cv_device_status",
    service_name="Arista CVP Status",
    discovery_function=discover_arista_cv_device_status,
    check_function=check_arista_cv_device_status,
    check_default_parameters=DEFAULT_PARAMS,
)
