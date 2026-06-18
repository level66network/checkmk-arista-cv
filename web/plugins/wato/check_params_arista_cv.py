"""checkmk 2.2 WATO check parameters: Arista CVP device status.

Covers both check plugins:
  - arista_cv_devices       (service on the CVP host, item = device hostname)
  - arista_cv_device_status (service on the device's own host via piggyback)

Both reference check_ruleset_name="arista_cv_device_status".
"""

from cmk.gui.i18n import _
from cmk.gui.plugins.wato.utils import (
    CheckParameterRulespecWithItem,
    RulespecGroupCheckParametersNetworking,
    rulespec_registry,
)
from cmk.gui.valuespec import Dictionary, DropdownChoice, TextInput


def _state_choice(title: str, help_text: str, default: int) -> DropdownChoice:
    return DropdownChoice(
        title=_(title),
        help=_(help_text),
        choices=[(0, _("OK")), (1, _("WARNING")), (2, _("CRITICAL"))],
        default_value=default,
    )


def _parameter_valuespec_arista_cv_device_status():
    return Dictionary(
        title=_("Arista CVP Device Status"),
        help=_(
            "Monitoring state for each CVP device condition. "
            "Rules are matched per host (piggyback) or per service item (CVP-host overview). "
            "The first matching rule wins."
        ),
        elements=[
            (
                "disconnected_state",
                _state_choice(
                    title="State when device is not connected",
                    help_text="CVP reports the device status as anything other than Connected or Registered.",
                    default=2,
                ),
            ),
            (
                "compliance_warning_state",
                _state_choice(
                    title="State for compliance indication: WARNING",
                    help_text="CVP detected a configlet mismatch or minor compliance discrepancy.",
                    default=1,
                ),
            ),
            (
                "compliance_error_state",
                _state_choice(
                    title="State for compliance indication: ERROR",
                    help_text="CVP detected a critical compliance error (running config significantly deviates from configlets).",
                    default=2,
                ),
            ),
            (
                "streaming_inactive_state",
                _state_choice(
                    title="State when streaming telemetry is inactive",
                    help_text="The device is not actively streaming telemetry data to CVP.",
                    default=1,
                ),
            ),
        ],
        optional_keys=[
            "disconnected_state",
            "compliance_warning_state",
            "compliance_error_state",
            "streaming_inactive_state",
        ],
    )


rulespec_registry.register(
    CheckParameterRulespecWithItem(
        check_group_name="arista_cv_device_status",
        group=RulespecGroupCheckParametersNetworking,
        item_spec=lambda: TextInput(
            title=_("Device hostname"),
            help=_(
                "The hostname of the CVP-managed device as reported by CVP. "
                "Leave empty to match all devices."
            ),
        ),
        parameter_valuespec=_parameter_valuespec_arista_cv_device_status,
        title=lambda: _("Arista CVP Device Status"),
    )
)
