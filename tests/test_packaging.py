from __future__ import annotations

import json
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
    assert "learnlab/collections/certifications.yaml" in names
    assert "learnlab/collections/proxmox/collection.yaml" in names
    assert "learnlab/collections/proxmox/courses/proxmox-admin/course.yaml" in names
    provider_prefix = "learnlab/collections/proxmox/courses/provider-bootstrap/"
    assert provider_prefix + "course.yaml" in names
    assert len(
        [
            name
            for name in names
            if name.startswith(provider_prefix + "lessons/")
            and name.endswith("/lesson.yaml")
        ]
    ) == 8
    canonical_curriculum = root / "src" / "learnlab" / "collections"
    installed_curriculum = tmp_path / "extracted" / "learnlab" / "collections"
    assert _curriculum_files(canonical_curriculum) == _curriculum_files(
        installed_curriculum
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

    cli_environment = smoke_environment.copy()
    cli_environment["PATH"] = os.pathsep.join(
        (str(installed / "bin"), cli_environment.get("PATH", ""))
    )
    help_result = subprocess.run(  # noqa: S603 - installed test artifact only
        [str(installed / "bin" / "learnlab"), "validate", "--help"],
        check=True,
        cwd=tmp_path,
        env=cli_environment,
        capture_output=True,
        text=True,
    )
    assert "Validate curriculum" in help_result.stdout
    assert "--provider" in help_result.stdout
    assert "--format" in help_result.stdout

    validation_result = subprocess.run(  # noqa: S603 - installed artifact only
        [str(installed / "bin" / "learnlab"), "validate", "--format", "json"],
        check=True,
        cwd=tmp_path,
        env=cli_environment,
        capture_output=True,
        text=True,
    )
    payload = json.loads(validation_result.stdout)
    assert set(payload) == {"schema_version", "ok", "findings"}
    assert payload["schema_version"] == 1
    assert payload["ok"] is True
    assert all(
        set(finding)
        == {
            "severity",
            "course_path",
            "source_path",
            "code",
            "message",
            "remedy",
        }
        for finding in payload["findings"]
    )

    pending_paths = (
        "nginx/nginx-basics",
        "nginx-nixos/nginx-basics",
        "nftables-debian13/nftables-basics",
        "nftables-nixos/nftables-basics",
        "systemd-debian/service-authoring",
        "systemd-nixos/service-authoring",
    )
    pending_smoke = subprocess.run(  # noqa: S603 - installed artifact only
        [
            sys.executable,
            "-c",
            """
import json
from importlib.resources import files
from unittest.mock import patch
from typer.testing import CliRunner
from learnlab import cli
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType
from learnlab.course_certification import CourseMaturity
from learnlab.state import StateStore
from pathlib import Path
root = files('learnlab') / 'collections'
assert root.joinpath('certifications.yaml').read_text().strip() == 'certifications: []'
catalog = CurriculumCatalog(root)
paths = json.loads(__import__('sys').argv[1])
for path in paths:
    course = catalog.load_course(path)
    assert course.maturity is CourseMaturity.DRAFT
    assert course.environment.guest_capabilities
    with (
        patch.object(cli, 'state_store_factory',
                     side_effect=AssertionError('state accessed')),
        patch.object(cli, 'load_settings',
                     side_effect=AssertionError('provider settings accessed')),
    ):
        result = CliRunner().invoke(cli.app, ['start', path])
    assert result.exit_code == 2, result.output
    assert 'not live-validated' in result.output
    assert '--include-drafts' in result.output
    print(path)
path = 'proxmox/nixos-template'
course = catalog.load_course(path)
assert course.maturity is CourseMaturity.DRAFT
assert [lesson.id for lesson in course.lessons] == [
    'prerequisites-and-safety', 'create-installer-vm', 'install-nixos',
    'configure-lab-access', 'seal-and-convert', 'test-two-clones',
    'configure-provider',
]
for lesson in course.lessons:
    policy = course.effective_environment(lesson)
    assert policy.scope is EnvironmentScope.NONE
    assert policy.provider_capability is None
    assert policy.guest_capabilities == ()
    assert all(check.type in (VerificationType.TEXT_EVIDENCE,
                             VerificationType.MANUAL_CONFIRMATION)
               for step in lesson.steps for check in step.verifications)
store = StateStore(Path('bootstrap-state/learnlab.db'))
def forbidden(*args, **kwargs):
    raise AssertionError('bootstrap accessed settings, provider, or SSH')
with (
    patch.object(cli, 'state_store_factory', return_value=store),
    patch.object(cli, 'state_root', return_value=Path('bootstrap-state')),
    patch.object(cli, 'load_settings', side_effect=forbidden),
    patch.object(cli, 'load_requested_profiles', side_effect=forbidden),
    patch.object(cli, 'resolve_token_secret', side_effect=forbidden),
    patch.object(cli, 'provider_factory', side_effect=forbidden),
    patch.object(cli, 'SshExecutor', side_effect=forbidden),
):
    started = CliRunner().invoke(cli.app, ['start', path, '--include-drafts'],
                                input='7\\n\\ny\\nq\\n')
    assert started.exit_code == 0, started.output
    assert 'PASS (self-attested): Learner confirmed' in started.output
    assert 'Progress saved.' in started.output
    step_path = ('proxmox', 'nixos-template', 'configure-provider', 'create-profile')
    [saved] = store.verification_records(step_path)
    assert saved.self_attested and saved.evidence is None
    resumed = CliRunner().invoke(cli.app, ['resume', path],
                                input='7\\n\\ny\\n\\ny\\n\\nself-attested\\nq\\n')
    assert resumed.exit_code == 0, resumed.output
    assert '[in progress]' in resumed.output
    assert 'create-profile' not in resumed.output
    assert 'read-only-handoff-checked' in resumed.output
    assert store.verification_records(step_path) == [saved]
    assert store.completed_lessons('proxmox', 'nixos-template') == {
        'configure-provider'
    }
    assert catalog.load_course(path).maturity is CourseMaturity.DRAFT
    assert (root.joinpath('certifications.yaml').read_text().strip()
            == 'certifications: []')
    gated = CliRunner().invoke(cli.app, ['start', path])
    assert gated.exit_code == 2, gated.output
    assert 'not live-validated' in gated.output
print(path + ': none; draft; start/save/resume; self-attested')
path = 'proxmox/provider-bootstrap'
course = catalog.load_course(path)
assert course.maturity is CourseMaturity.DRAFT
assert [lesson.id for lesson in course.lessons] == [
    'safety-and-private-worksheet', 'read-only-inventory',
    'map-provider-authority', 'create-identity-roles-and-acls',
    'add-named-profile', 'run-get-only-health',
    'authorize-scratch-lifecycle', 'reconcile-and-rollback',
]
for lesson in course.lessons:
    policy = course.effective_environment(lesson)
    assert policy.scope is EnvironmentScope.NONE
    assert policy.provider_capability is None
    assert policy.guest_capabilities == ()
    assert all(check.type in (VerificationType.TEXT_EVIDENCE,
                             VerificationType.MANUAL_CONFIRMATION)
               for step in lesson.steps for check in step.verifications)
provider_store = StateStore(Path('provider-bootstrap-state/learnlab.db'))
def provider_forbidden(*args, **kwargs):
    raise AssertionError('provider bootstrap accessed an external dependency')
with (
    patch.object(cli, 'state_store_factory', return_value=provider_store),
    patch.object(cli, 'state_root', return_value=Path('provider-bootstrap-state')),
    patch.object(cli, 'load_settings', side_effect=provider_forbidden),
    patch.object(cli, 'load_requested_profiles', side_effect=provider_forbidden),
    patch.object(cli, 'resolve_token_secret', side_effect=provider_forbidden),
    patch.object(cli, 'provider_factory', side_effect=provider_forbidden),
    patch.object(cli, 'SshExecutor', side_effect=provider_forbidden),
    patch('learnlab.providers.proxmox.httpx.Client', side_effect=provider_forbidden),
):
    gated = CliRunner().invoke(cli.app, ['start', path])
    assert gated.exit_code == 2, gated.output
    assert '--include-drafts' in gated.output
    started = CliRunner().invoke(
        cli.app, ['start', path, '--include-drafts'],
        input='1\\n\\nlearner-operated\\n\\ny\\nq\\n',
    )
    assert started.exit_code == 0, started.output
    step_path = ('proxmox', 'provider-bootstrap',
                 'safety-and-private-worksheet', 'prepare-private-worksheet')
    [saved] = provider_store.verification_records(step_path)
    assert saved.self_attested and saved.evidence is None
    resumed = CliRunner().invoke(
        cli.app, ['resume', path], input='1\\n\\ny\\nq\\n'
    )
    assert resumed.exit_code == 0, resumed.output
    assert 'prepare-private-worksheet' not in resumed.output
    assert provider_store.verification_records(step_path) == [saved]
assert catalog.load_course(path).maturity is CourseMaturity.DRAFT
assert root.joinpath('certifications.yaml').read_text().strip() == 'certifications: []'
print(path + ': none; draft; start/save/resume; self-attested')
""",
            json.dumps(pending_paths),
        ],
        check=True,
        cwd=tmp_path,
        env=smoke_environment,
        capture_output=True,
        text=True,
    )
    assert pending_smoke.stdout.splitlines() == [
        *pending_paths,
        "proxmox/nixos-template: none; draft; start/save/resume; self-attested",
        "proxmox/provider-bootstrap: none; draft; start/save/resume; self-attested",
    ]
