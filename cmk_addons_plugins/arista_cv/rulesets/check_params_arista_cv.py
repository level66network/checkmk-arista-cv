"""checkmk 2.3+ ruleset: Arista CVP device status check parameters.

Covers both check plugins:
  - arista_cv_devices       (service on the CVP host, item = device hostname)
  - arista_cv_device_status (service on the device's own host via piggyback)

Both reference check_ruleset_name="arista_cv_device_status".
"""

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import DefaultValue, DictElement, Dictionary

# MonitoringState was renamed to ServiceState in checkmk 2.4
try:
    from cmk.rulesets.v1.form_specs import ServiceState as MonitoringState
except ImportError:
    from cmk.rulesets.v1.form_specs import MonitoringState  # type: ignore[no-redef]
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, Topic


def _state_element(title: str, help_text: str, default: int) -> DictElement:
    return DictElement(
        parameter_form=MonitoringState(
            title=Title(title),
            help_text=Help(help_text),
            prefill=DefaultValue(default),
        ),
        required=False,
    )


def _parameter_form() -> Dictionary:
    return Dictionary(
        title=Title("Arista CVP Device Status"),
        help_text=Help(
            "Monitoring state for each CVP device condition. "
            "Rules are matched per host (piggyback) or per service item (CVP-host overview). "
            "The first matching rule wins."
        ),
        elements={
            "disconnected_state": _state_element(
                title="State when device is not connected",
                help_text="CVP reports the device status as anything other than Connected or Registered.",
                default=2,
            ),
            "compliance_warning_state": _state_element(
                title="State for compliance indication: WARNING",
                help_text="CVP detected a configlet mismatch or minor compliance discrepancy.",
                default=1,
            ),
            "compliance_error_state": _state_element(
                title="State for compliance indication: ERROR",
                help_text="CVP detected a critical compliance error (running config significantly deviates from configlets).",
                default=2,
            ),
            "streaming_inactive_state": _state_element(
                title="State when streaming telemetry is inactive",
                help_text="The device is not actively streaming telemetry data to CVP.",
                default=1,
            ),
        },
    )


rule_spec_arista_cv_device_status = CheckParameters(
    name="arista_cv_device_status",
    title=Title("Arista CVP Device Status"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form,
    condition=HostAndItemCondition(item_title=Title("Device hostname")),
)
