"""checkmk check plugin: Arista CVP system information.

Single service per CVP host reporting the CVP software version.
Service name: "Arista CVP Info"
"""

import json
from typing import Dict, Optional

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

Section = Dict[str, str]


def parse_arista_cv_info(string_table: StringTable) -> Optional[Section]:
    if not string_table:
        return None

    try:
        data = json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError, KeyError):
        return None

    if not isinstance(data, dict):
        return None

    return data


def discover_arista_cv_info(section: Optional[Section]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def check_arista_cv_info(section: Optional[Section]) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No CVP system info available")
        return

    version = section.get("version", "unknown")
    node = section.get("cvpNodeAddress", "unknown")

    yield Result(
        state=State.OK,
        summary=f"Version: {version}",
        details=f"Node: {node} | Version: {version}",
    )


agent_section_arista_cv_info = AgentSection(
    name="arista_cv_info",
    parse_function=parse_arista_cv_info,
)

check_plugin_arista_cv_info = CheckPlugin(
    name="arista_cv_info",
    service_name="Arista CVP Info",
    discovery_function=discover_arista_cv_info,
    check_function=check_arista_cv_info,
)
