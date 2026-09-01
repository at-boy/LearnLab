from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path


def _curriculum_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_authoring_and_packaged_curriculum_trees_are_byte_identical() -> None:
    root = Path(__file__).parents[1]

    assert _curriculum_files(root / "collections") == _curriculum_files(
        root / "src" / "learnlab" / "collections"
    )


def test_readme_documents_interactive_lifecycle_feedback() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    for concept in (
        "lifecycle feedback",
        "retry attempt",
        "elapsed time",
        "ready",
        "interactive terminal",
        "newline-delimited",
    ):
        assert concept in readme


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
        archive.extractall(tmp_path / "extracted")  # noqa: S202 - test wheel only
    assert "learnlab/collections/proxmox/collection.yaml" in names
    assert "learnlab/collections/proxmox/courses/proxmox-admin/course.yaml" in names
    assert _curriculum_files(root / "collections") == _curriculum_files(
        tmp_path / "extracted" / "learnlab" / "collections"
    )

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
                "from learnlab.curriculum import CurriculumCatalog; "
                "from importlib.resources import files; "
                "course = CurriculumCatalog(files('learnlab') / 'collections')"
                ".load_course('proxmox/proxmox-admin'); "
                "print(course.environment.scope.value); "
                "print(','.join(check.type.value for check in "
                "course.lessons[0].steps[0].verifications))"
            ),
        ],
        check=True,
        cwd=tmp_path,
        env=smoke_environment,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == [
        "course",
        "remote-command,remote-command,provider-check,provider-check,"
        "text-evidence,manual-confirmation",
    ]
