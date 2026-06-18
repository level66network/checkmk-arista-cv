#!/usr/bin/env python3
"""Build script — produces arista_cv-<version>.mkp.

A checkmk MKP is a gzipped tar archive with this internal layout:

  info                        Python pprint dict describing the package
  info.json                   JSON version of the same metadata (required by Exchange)
  agents.tar                  files for local/agents/
  cmk_addons_plugins.tar      files for local/lib/python3/cmk/plugins/

Run from the repo root:
  python3 build_mkp.py
"""

import io
import json
import pprint
import sys
import tarfile
from pathlib import Path

# ── Package metadata ──────────────────────────────────────────────────────────

PACKAGE_INFO: dict = {
    "author": "level66.network UG (haftungsbeschränkt)",
    "description": (
        "Special agent and check plugins for Arista CloudVision (CVP / CVaaS). "
        "Monitors device connection status, compliance, streaming telemetry, "
        "pending tasks, and last contact time per device. Supports "
        "username/password and service account token auth for CloudVision Portal (CVP), "
        "and token auth for CloudVision as a Service (CVaaS). Includes piggyback mode "
        "so each managed device gets its own checkmk host with an Arista CVP Status service."
    ),
    "download_url": "https://github.com/level66network/checkmk-arista-cv",
    "files": {
        "agents": [
            "special/agent_arista_cv",
        ],
        "cmk_addons_plugins": [
            "arista_cv/__init__.py",
            "arista_cv/agent_based/__init__.py",
            "arista_cv/agent_based/arista_cv_devices.py",
            "arista_cv/agent_based/arista_cv_device_status.py",
            "arista_cv/agent_based/arista_cv_info.py",
            "arista_cv/rulesets/__init__.py",
            "arista_cv/rulesets/special_agent_arista_cv.py",
            "arista_cv/rulesets/check_params_arista_cv.py",
            "arista_cv/server_side_calls/__init__.py",
            "arista_cv/server_side_calls/special_agent_arista_cv.py",
        ],
        "lib": [
            "python3/cvprac/__init__.py",
            "python3/cvprac/cvp_api.py",
            "python3/cvprac/cvp_client.py",
            "python3/cvprac/cvp_client_errors.py",
        ],
    },
    "name": "arista_cv",
    "title": "Arista CloudVision (CVP / CVaaS)",
    "version": "1.0.5",
    "version.min_required": "2.3.0p0",
    "version.packaged": "2.5.0p6",
    "version.usable_until": None,
}

# Map MKP category name → source subdirectory in this repo
_CATEGORY_SOURCE: dict = {
    "agents": "agents",
    "cmk_addons_plugins": "cmk_addons_plugins",
    "lib": "lib",
}


# ── Build logic ───────────────────────────────────────────────────────────────

def _make_category_tar(base_dir: Path, category: str, rel_paths: list) -> bytes:
    """Return the raw bytes of a category sub-tarball."""
    buf = io.BytesIO()
    source_root = base_dir / _CATEGORY_SOURCE[category]
    with tarfile.open(fileobj=buf, mode="w") as cat:
        for rel in rel_paths:
            abs_path = source_root / rel
            if not abs_path.exists():
                raise FileNotFoundError(f"Missing file for package: {abs_path}")
            cat.add(abs_path, arcname=rel)
    return buf.getvalue()


def build(base_dir: Path) -> Path:
    name = PACKAGE_INFO["name"]
    version = PACKAGE_INFO["version"]
    output = base_dir / f"{name}-{version}.mkp"

    with tarfile.open(output, "w:gz") as mkp:
        # info file — Python pprint dict (legacy format, still required)
        info_bytes = pprint.pformat(PACKAGE_INFO).encode("utf-8")
        ti = tarfile.TarInfo(name="info")
        ti.size = len(info_bytes)
        mkp.addfile(ti, io.BytesIO(info_bytes))

        # info.json — JSON manifest required by checkmk Exchange validator
        info_json_bytes = json.dumps(PACKAGE_INFO, ensure_ascii=False).encode("utf-8")
        ti = tarfile.TarInfo(name="info.json")
        ti.size = len(info_json_bytes)
        mkp.addfile(ti, io.BytesIO(info_json_bytes))

        # one sub-tarball per category
        for category, rel_paths in PACKAGE_INFO["files"].items():
            cat_bytes = _make_category_tar(base_dir, category, rel_paths)
            ti = tarfile.TarInfo(name=f"{category}.tar")
            ti.size = len(cat_bytes)
            mkp.addfile(ti, io.BytesIO(cat_bytes))

    return output


if __name__ == "__main__":
    base = Path(__file__).parent
    try:
        out = build(base)
        print(f"Built: {out}")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
