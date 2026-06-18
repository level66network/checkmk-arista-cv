"""Server-side call: translate ruleset parameters into agent_arista_cv CLI arguments."""

from collections.abc import Iterator

from cmk.server_side_calls.v1 import HostConfig, Secret, SpecialAgentCommand, SpecialAgentConfig


def _inline_secret(value):
    """Return Secret with pass_safely=False so the framework inlines the raw value.

    Explicit passwords are not in the password store, so pass_safely=True would
    produce an unresolvable uuid:path reference at runtime.
    """
    if isinstance(value, Secret):
        return Secret(id=value.id, format=value.format, pass_safely=False)
    return value


def _extract_secrets(params: dict) -> dict:
    deployment_type, deployment_params = params["deployment"]

    if deployment_type == "cvaas":
        deployment_params = {
            **deployment_params,
            "token": _inline_secret(deployment_params["token"]),
        }
    else:
        cred_type, cred_params = deployment_params["credentials"]
        if cred_type == "token":
            cred_params = {**cred_params, "token": _inline_secret(cred_params["token"])}
        else:
            cred_params = {**cred_params, "password": _inline_secret(cred_params["password"])}
        deployment_params = {**deployment_params, "credentials": (cred_type, cred_params)}

    return {**params, "deployment": (deployment_type, deployment_params)}


def _generate_arista_cv_commands(
    params: dict, host_config: HostConfig
) -> Iterator[SpecialAgentCommand]:
    deployment_type, deployment_params = params["deployment"]
    args: list = []

    if deployment_type == "cvaas":
        args += ["--hostname", deployment_params["endpoint"]]
        args += ["--token", deployment_params["token"]]
        args.append("--cvaas")
    else:
        args += ["--hostname", deployment_params["hostname"]]
        cred_type, cred_params = deployment_params["credentials"]
        if cred_type == "token":
            args += ["--token", cred_params["token"]]
        else:
            args += ["--username", cred_params["username"]]
            args += ["--password", cred_params["password"]]
        if "port" in deployment_params:
            args += ["--port", str(deployment_params["port"])]
        if deployment_params.get("no_tls_verify"):
            args.append("--no-tls-verify")

    pb = params.get("piggyback", {})
    if pb.get("enabled"):
        args.append("--piggyback")
        args += ["--piggyback-name", pb.get("name", "hostname")]

    yield SpecialAgentCommand(command_arguments=args)


special_agent_arista_cv = SpecialAgentConfig(
    name="arista_cv",
    parameter_parser=_extract_secrets,
    commands_function=_generate_arista_cv_commands,
)
