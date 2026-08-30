from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path


def test_built_wheel_installs_with_curriculum_resources(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    build_environment = os.environ.copy()
    fallback_site = root / ".venv" / "lib" / "python3.13" / "site-packages"
    if fallback_site.is_dir():
        existing = build_environment.get("PYTHONPATH")
        build_environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(fallback_site), existing) if value
        )
    subprocess.run(  # noqa: S603 - fixed interpreter and repository paths
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(root),
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
        ],
        check=True,
        cwd=tmp_path,
        env=build_environment,
        capture_output=True,
        text=True,
    )
    [wheel] = wheel_dir.glob("learnlab-*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert "learnlab/collections/proxmox/collection.yaml" in names
    assert "learnlab/collections/proxmox/courses/proxmox-admin/course.yaml" in names

    installed = tmp_path / "installed"
    subprocess.run(  # noqa: S603 - fixed interpreter and wheel path
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    smoke_environment = os.environ.copy()
    smoke_environment["PYTHONPATH"] = str(installed)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from learnlab.cli import _default_catalog; "
                "course = _default_catalog().load_course('proxmox/proxmox-admin'); "
                "print(course.id, course.requirements)"
            ),
        ],
        check=True,
        cwd=tmp_path,
        env=smoke_environment,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "proxmox-admin ('proxmox.api',)"
