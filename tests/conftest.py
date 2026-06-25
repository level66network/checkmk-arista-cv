"""Shared test fixtures for the Arista CloudVision plugin.

Two awkward import situations are handled here:

1. The special agent ships as ``agents/special/agent_arista_cv`` with no ``.py``
   extension, so it is loaded by file path via importlib.

2. The check plugin imports ``cmk.agent_based.v2``, which is only present on a
   checkmk server. Tests inject a minimal stub of that module into
   ``sys.modules`` so the plugin can be imported and its glue exercised off-box.
   The pure policy logic (``classify_expiry``) needs none of this.
"""

import base64
import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_PATH = REPO_ROOT / "agents" / "special" / "agent_arista_cv"
CHECK_PATH = (
    REPO_ROOT
    / "cmk_addons_plugins"
    / "arista_cv"
    / "agent_based"
    / "arista_cv_token.py"
)


def _load_module_from_path(name: str, path: Path):
    # SourceFileLoader is required because the agent script has no .py extension,
    # which would otherwise yield a spec with no loader.
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def agent():
    """The special agent module (helpers only; main() is not invoked)."""
    return _load_module_from_path("agent_arista_cv", AGENT_PATH)


def _install_cmk_stub():
    """Install a minimal stand-in for cmk.agent_based.v2 used by the plugin.

    The stub mirrors the real API *shapes* (State is an IntEnum 0..3; Result,
    Metric, Service record their kwargs) so tests can assert on what the plugin
    yields. It is not a behavioral mock of checkmk.
    """
    if "cmk.agent_based.v2" in sys.modules:
        return

    import enum
    import dataclasses

    mod = types.ModuleType("cmk.agent_based.v2")

    class State(enum.IntEnum):
        OK = 0
        WARN = 1
        CRIT = 2
        UNKNOWN = 3

    @dataclasses.dataclass
    class Result:
        state: State
        summary: str = ""
        details: str = ""
        notice: str = ""

    @dataclasses.dataclass
    class Metric:
        name: str
        value: float
        levels: object = None
        boundaries: object = None

    @dataclasses.dataclass
    class Service:
        item: object = None

    class _Registrable:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    mod.State = State
    mod.Result = Result
    mod.Metric = Metric
    mod.Service = Service
    mod.AgentSection = _Registrable
    mod.CheckPlugin = _Registrable
    mod.CheckResult = object
    mod.DiscoveryResult = object
    mod.StringTable = list

    cmk_pkg = sys.modules.setdefault("cmk", types.ModuleType("cmk"))
    agent_based_pkg = sys.modules.setdefault(
        "cmk.agent_based", types.ModuleType("cmk.agent_based")
    )
    cmk_pkg.agent_based = agent_based_pkg
    agent_based_pkg.v2 = mod
    sys.modules["cmk.agent_based.v2"] = mod


@pytest.fixture(scope="session")
def check():
    """The arista_cv_token check plugin module, importable via the cmk stub."""
    _install_cmk_stub()
    return _load_module_from_path("arista_cv_token", CHECK_PATH)


def make_jwt(payload: dict) -> str:
    """Build an unsigned JWT-shaped token string with the given payload."""

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = b64(json.dumps(payload).encode())
    return f"{header}.{body}.signature"
