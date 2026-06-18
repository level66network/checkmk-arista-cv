"""checkmk 2.2 WATO rule: Arista CloudVision (CVP / CVaaS) special agent."""

from cmk.gui.i18n import _
from cmk.gui.plugins.wato.utils import (
    HostRulespec,
    RulespecGroupDatasourceProgramsNetworking,
    rulespec_registry,
)
from cmk.gui.valuespec import (
    CascadingDropdown,
    Checkbox,
    Dictionary,
    DropdownChoice,
    Integer,
    Password,
    TextInput,
)

_CVAAS_ENDPOINT_HELP = _(
    "Regional CVaaS hostname. Known endpoints: "
    "www.arista.io (US 1a), "
    "www.cv-prod-us-central1-c.arista.io (US 1c), "
    "www.cv-prod-na-northeast1-b.arista.io (Canada), "
    "www.cv-prod-euwest-2.arista.io (Europe West 2), "
    "www.cv-prod-apnortheast-1.arista.io (Japan), "
    "www.cv-prod-ausoutheast-1.arista.io (Australia). "
    "URLs without 'www' are not supported."
)


def _on_prem_dict():
    return Dictionary(
        elements=[
            (
                "hostname",
                TextInput(
                    title=_("CVP hostname"),
                    help=_("Hostname or IP address of the CVP node or cluster VIP."),
                    allow_empty=False,
                ),
            ),
            (
                "credentials",
                CascadingDropdown(
                    title=_("Authentication"),
                    help=_(
                        "Service account tokens are recommended for automation; "
                        "they are generated under Settings > Access Control > "
                        "Service Accounts in CVP."
                    ),
                    choices=[
                        (
                            "password",
                            _("Username / Password"),
                            Dictionary(
                                elements=[
                                    (
                                        "username",
                                        TextInput(
                                            title=_("Username"),
                                            help=_("CVP local or LDAP username."),
                                            allow_empty=False,
                                        ),
                                    ),
                                    (
                                        "password",
                                        Password(
                                            title=_("Password"),
                                            allow_empty=False,
                                        ),
                                    ),
                                ],
                                required_keys=["username", "password"],
                                optional_keys=[],
                            ),
                        ),
                        (
                            "token",
                            _("Service Account Token"),
                            Dictionary(
                                elements=[
                                    (
                                        "token",
                                        Password(
                                            title=_("Token"),
                                            help=_(
                                                "CVP service account token. "
                                                "Available from CVP 2020.3.0 and later."
                                            ),
                                            allow_empty=False,
                                        ),
                                    ),
                                ],
                                required_keys=["token"],
                                optional_keys=[],
                            ),
                        ),
                    ],
                    default_value=("password", {}),
                ),
            ),
            (
                "port",
                Integer(
                    title=_("HTTPS port"),
                    help=_("TCP port for the CVP HTTPS API. Default is 443."),
                    default_value=443,
                    minvalue=1,
                    maxvalue=65535,
                ),
            ),
            (
                "no_tls_verify",
                Checkbox(
                    title=_("Disable TLS certificate verification"),
                    help=_(
                        "Enable only for lab/self-signed certificate environments. "
                        "Not recommended in production."
                    ),
                    default_value=False,
                ),
            ),
        ],
        required_keys=["hostname", "credentials"],
        optional_keys=["port", "no_tls_verify"],
    )


def _cvaas_dict():
    return Dictionary(
        elements=[
            (
                "endpoint",
                TextInput(
                    title=_("CVaaS endpoint"),
                    help=_CVAAS_ENDPOINT_HELP,
                    allow_empty=False,
                ),
            ),
            (
                "token",
                Password(
                    title=_("Service account token"),
                    help=_("CVaaS service account token."),
                    allow_empty=False,
                ),
            ),
        ],
        required_keys=["endpoint", "token"],
        optional_keys=[],
    )


def _valuespec_special_agent_arista_cv():
    return Dictionary(
        title=_("Arista CloudVision (CVP / CVaaS)"),
        help=_(
            "Special agent for Arista CloudVision — either a self-hosted CVP instance "
            "or CloudVision as a Service (CVaaS)."
        ),
        elements=[
            (
                "deployment",
                CascadingDropdown(
                    title=_("Deployment type"),
                    choices=[
                        ("on_prem", _("CloudVision Portal (CVP)"), _on_prem_dict()),
                        ("cvaas", _("CloudVision as a Service (CVaaS)"), _cvaas_dict()),
                    ],
                    default_value=("on_prem", {}),
                ),
            ),
            (
                "piggyback",
                Checkbox(
                    title=_("Enable piggyback mode"),
                    label=_("Emit per-device piggyback sections"),
                    help=_(
                        "When enabled, the agent outputs a piggyback block for every "
                        "CVP-managed device. checkmk routes each block to the matching "
                        "host, giving it an \"Arista CVP Status\" service. "
                        "The device host must already exist in checkmk and its name "
                        "must match the field chosen below."
                    ),
                    default_value=False,
                ),
            ),
            (
                "piggyback_name",
                DropdownChoice(
                    title=_("Piggyback host identifier"),
                    help=_(
                        "Which CVP field to use as the piggyback host name. "
                        "It must match the checkmk host name exactly."
                    ),
                    choices=[
                        ("hostname", _("Hostname (short name reported by CVP)")),
                        ("fqdn", _("FQDN (fully qualified domain name)")),
                        ("ipaddress", _("IP address")),
                    ],
                    default_value="hostname",
                ),
            ),
        ],
        required_keys=["deployment"],
        optional_keys=["piggyback", "piggyback_name"],
    )


rulespec_registry.register(
    HostRulespec(
        group=RulespecGroupDatasourceProgramsNetworking,
        name="special_agents:arista_cv",
        valuespec=_valuespec_special_agent_arista_cv,
        title=lambda: _("Arista CloudVision (CVP / CVaaS)"),
    )
)
