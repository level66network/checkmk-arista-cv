"""checkmk ruleset: Arista CVP / CVaaS service account token expiry parameters.

Shared by both token check plugins (mirrors how arista_cv_device_status serves
both the itemless and itemized device plugins):
  - arista_cv_token            (itemless, the agent's own auth token)
  - arista_cv_service_tokens   (item = "<user> / <description>")

Both reference check_ruleset_name="arista_cv_token".
"""

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import DefaultValue, DictElement, Dictionary, Integer
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, Topic


def _parameter_form() -> Dictionary:
    return Dictionary(
        title=Title("Arista CVP Token"),
        help_text=Help(
            "Warn ahead of service account token expiry. Applies to the token the "
            "special agent authenticates with and, where the Resource API is "
            "available, to every service account token in the CVP/CVaaS instance."
        ),
        elements={
            "warn_days": DictElement(
                parameter_form=Integer(
                    title=Title("Warn when expiring within (days)"),
                    help_text=Help(
                        "Warning state once a token expires in this many days or fewer."
                    ),
                    prefill=DefaultValue(14),
                    unit_symbol="days",
                ),
                required=False,
            ),
            "crit_days": DictElement(
                parameter_form=Integer(
                    title=Title("Critical when expiring within (days)"),
                    help_text=Help(
                        "Critical state once a token expires in this many days or "
                        "fewer (also covers already-expired tokens)."
                    ),
                    prefill=DefaultValue(4),
                    unit_symbol="days",
                ),
                required=False,
            ),
        },
    )


rule_spec_arista_cv_token = CheckParameters(
    name="arista_cv_token",
    title=Title("Arista CVP Token"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form,
    condition=HostAndItemCondition(item_title=Title("Token")),
)
