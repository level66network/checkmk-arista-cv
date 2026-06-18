"""checkmk 2.3+ ruleset: Arista CloudVision (CVP / CVaaS) special agent."""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    CascadingSingleChoice,
    CascadingSingleChoiceElement,
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    Password,
    SingleChoice,
    SingleChoiceElement,
    String,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic

_CVAAS_ENDPOINT_HELP = (
    "Regional CVaaS hostname. Known endpoints: "
    "www.arista.io (US 1a), "
    "www.cv-prod-us-central1-c.arista.io (US 1c), "
    "www.cv-prod-na-northeast1-b.arista.io (Canada), "
    "www.cv-prod-euwest-2.arista.io (Europe West 2), "
    "www.cv-prod-apnortheast-1.arista.io (Japan), "
    "www.cv-prod-ausoutheast-1.arista.io (Australia). "
    "URLs without 'www' are not supported."
)


def _on_prem_form() -> Dictionary:
    return Dictionary(
        elements={
            "hostname": DictElement(
                parameter_form=String(
                    title=Title("CVP hostname"),
                    help_text=Help("Hostname or IP address of the CVP node or cluster VIP."),
                ),
                required=True,
            ),
            "credentials": DictElement(
                parameter_form=CascadingSingleChoice(
                    title=Title("Authentication"),
                    help_text=Help(
                        "Service account tokens are recommended for automation; "
                        "they are generated under Settings > Access Control > "
                        "Service Accounts in CVP."
                    ),
                    elements=[
                        CascadingSingleChoiceElement(
                            name="password",
                            title=Title("Username / Password"),
                            parameter_form=Dictionary(
                                elements={
                                    "username": DictElement(
                                        parameter_form=String(
                                            title=Title("Username"),
                                            help_text=Help("CVP local or LDAP username."),
                                        ),
                                        required=True,
                                    ),
                                    "password": DictElement(
                                        parameter_form=Password(title=Title("Password")),
                                        required=True,
                                    ),
                                }
                            ),
                        ),
                        CascadingSingleChoiceElement(
                            name="token",
                            title=Title("Service Account Token"),
                            parameter_form=Dictionary(
                                elements={
                                    "token": DictElement(
                                        parameter_form=Password(
                                            title=Title("Token"),
                                            help_text=Help(
                                                "CVP service account token. "
                                                "Available from CVP 2020.3.0 and later."
                                            ),
                                        ),
                                        required=True,
                                    ),
                                }
                            ),
                        ),
                    ],
                    prefill=DefaultValue("password"),
                ),
                required=True,
            ),
            "port": DictElement(
                parameter_form=Integer(
                    title=Title("HTTPS port"),
                    help_text=Help("TCP port for the CVP HTTPS API. Default is 443."),
                    prefill=DefaultValue(443),
                ),
                required=False,
            ),
            "no_tls_verify": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Disable TLS certificate verification"),
                    help_text=Help(
                        "Enable only for lab/self-signed certificate environments. "
                        "Not recommended in production."
                    ),
                    prefill=DefaultValue(False),
                ),
                required=True,
            ),
        }
    )


def _cvaas_form() -> Dictionary:
    return Dictionary(
        elements={
            "endpoint": DictElement(
                parameter_form=String(
                    title=Title("CVaaS endpoint"),
                    help_text=Help(_CVAAS_ENDPOINT_HELP),
                ),
                required=True,
            ),
            "token": DictElement(
                parameter_form=Password(
                    title=Title("Service account token"),
                    help_text=Help("CVaaS service account token."),
                ),
                required=True,
            ),
        }
    )


def _parameter_form() -> Dictionary:
    return Dictionary(
        title=Title("Arista CloudVision (CVP / CVaaS)"),
        help_text=Help(
            "Special agent for Arista CloudVision — either a self-hosted CVP instance "
            "or CloudVision as a Service (CVaaS)."
        ),
        elements={
            "deployment": DictElement(
                parameter_form=CascadingSingleChoice(
                    title=Title("Deployment type"),
                    elements=[
                        CascadingSingleChoiceElement(
                            name="on_prem",
                            title=Title("CloudVision Portal (CVP)"),
                            parameter_form=_on_prem_form(),
                        ),
                        CascadingSingleChoiceElement(
                            name="cvaas",
                            title=Title("CloudVision as a Service (CVaaS)"),
                            parameter_form=_cvaas_form(),
                        ),
                    ],
                    prefill=DefaultValue("on_prem"),
                ),
                required=True,
            ),
            "piggyback": DictElement(
                parameter_form=Dictionary(
                    title=Title("Piggyback mode"),
                    help_text=Help(
                        "When enabled, the agent outputs one piggyback block per "
                        "CVP-managed device. checkmk routes each block to the matching "
                        "host, giving it an \"Arista CVP Status\" service."
                    ),
                    elements={
                        "enabled": DictElement(
                            parameter_form=BooleanChoice(
                                title=Title("Enable"),
                                label=Label("Emit per-device piggyback sections"),
                                prefill=DefaultValue(False),
                            ),
                            required=True,
                        ),
                        "name": DictElement(
                            parameter_form=SingleChoice(
                                title=Title("Host identifier"),
                                help_text=Help(
                                    "Which CVP field to use as the piggyback host name. "
                                    "It must match the checkmk host name exactly."
                                ),
                                elements=[
                                    SingleChoiceElement(
                                        name="hostname",
                                        title=Title("Hostname (short name reported by CVP)"),
                                    ),
                                    SingleChoiceElement(
                                        name="fqdn",
                                        title=Title("FQDN (fully qualified domain name)"),
                                    ),
                                    SingleChoiceElement(
                                        name="ipaddress",
                                        title=Title("IP address"),
                                    ),
                                ],
                                prefill=DefaultValue("hostname"),
                            ),
                            required=True,
                        ),
                    },
                ),
                required=True,
            ),
        },
    )


rule_spec_arista_cv = SpecialAgent(
    name="arista_cv",
    title=Title("Arista CloudVision (CVP / CVaaS)"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form,
)
