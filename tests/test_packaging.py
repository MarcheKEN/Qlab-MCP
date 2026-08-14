from __future__ import annotations

from pathlib import Path
import os
import subprocess
import tarfile
import tomllib
from zipfile import ZipFile

import qlab_mcp
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_project_module_and_lock_versions_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    locked_project = next(package for package in lock["package"] if package["name"] == "qlab-mcp")

    assert project["project"]["version"] == "0.3.0"
    assert qlab_mcp.__version__ == "0.3.0"
    assert locked_project["version"] == qlab_mcp.__version__


def test_build_artifacts_contain_only_release_files(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    try:
        subprocess.run(
            ["uv", "build", "--out-dir", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", "/tmp/qlab-uv-cache")},
        )
    except subprocess.CalledProcessError as exc:
        if "Operation not permitted" in exc.stderr or "dns error" in exc.stderr:
            pytest.skip("uv build dependencies unavailable in this sandbox")
        raise

    wheel = next(output.glob("*.whl"))
    with ZipFile(wheel) as archive:
        wheel_members = set(archive.namelist())
        assert wheel_members
        assert all(
            name.startswith("qlab_mcp/") or name.startswith("qlab_mcp-0.3.0.dist-info/")
            for name in wheel_members
        )
        metadata = archive.read("qlab_mcp-0.3.0.dist-info/METADATA").decode()
        assert "Version: 0.3.0\n" in metadata

    sdist = next(output.glob("*.tar.gz"))
    with tarfile.open(sdist, "r:gz") as archive:
        prefix = "qlab_mcp-0.3.0/"
        members = {member.name.removeprefix(prefix) for member in archive.getmembers()}
        assert members
        assert all(
            name.startswith("src/qlab_mcp/")
            or name in {".gitignore", "README.md", "pyproject.toml", "PKG-INFO"}
            for name in members
        )
        assert not any(
            name.startswith((".codex/", "engineering-review/", "local/"))
            for name in members
        )
