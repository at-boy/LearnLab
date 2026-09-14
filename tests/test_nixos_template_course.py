import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from learnlab.course_certification import CourseMaturity
from learnlab.course_validation import validate_catalog
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/nixos-template"


def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)


def lesson_text(lesson_id):
    lessons = {item.id: item for item in load_course().lessons}
    assert lesson_id in lessons, f"Missing required lesson: {lesson_id}"
    lesson = lessons[lesson_id]
    return "\n".join(step.instructions for step in lesson.steps)


def hostid_script(source):
    text = (
        lesson_text("install-nixos")
        if source == "course"
        else (Path(__file__).parents[1] / "docs/NixOS-Template-Guide.md").read_text()
    )
    match = re.search(r"script = ''\n(.*?)\n\s*'';", text, re.DOTALL)
    assert match, "The installed configuration needs its persistent hostid oneshot"
    script = textwrap.dedent(match[1])
    assert "${" not in script.replace("''${", ""), "Unescaped Nix interpolation"
    return script.replace("''${", "${")


@pytest.fixture(params=["course", "guide"])
def hostid_sandbox(tmp_path, request):
    # Only ownership operations are stubbed: binary writes, validation, cleanup,
    # permissions and rename execute for real under this private directory.
    etc = tmp_path / "etc"
    etc.mkdir()
    etc.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "stat": """#!/bin/bash
if [[ "$1" == -c && "$2" == %u ]]; then
  printf '%s\\n' "${TEST_OWNER:-0}"
else
  exec /usr/bin/stat "$@"
fi
""",
        "chown": """#!/bin/bash
[[ "$1" == root:root && "$2" == "$TEST_ETC"/.learnlab-hostid.* ]] || exit 90
[[ "${TEST_FAIL:-}" != chown ]]
""",
        "mv": """#!/bin/bash
[[ "${TEST_FAIL:-}" != mv ]] || exit 91
exec /usr/bin/mv "$@"
""",
    }.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o700)
    env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin", "TEST_ETC": str(etc)}

    def run(**overrides):
        script = hostid_script(request.param).replace("/etc", str(etc))
        return subprocess.run(  # noqa: S603
            ["/bin/bash", "-c", script],
            env={**env, **overrides},
            capture_output=True,
            text=True,
            timeout=5,
        )

    return etc, run


def test_hostid_derives_little_endian_first_eight_and_preserves_existing(
    hostid_sandbox,
):
    etc, run = hostid_sandbox
    # Synthetic fixture; bytes and expected integer are independently hand-derived.
    (etc / "machine-id").write_text("1234abcd" + "0" * 24 + "\n")
    result = run()
    assert result.returncode == 0, result.stderr
    target = etc / "hostid"
    assert target.read_bytes() == b"\xcd\xab\x34\x12"
    assert target.stat().st_mode & 0o777 == 0o444
    assert target.stat().st_nlink == 1
    (etc / "machine-id").write_text("abcdef12" + "0" * 24)
    assert run().returncode != 0  # Systemd normally skips this existing target.
    assert target.read_bytes() == b"\xcd\xab\x34\x12"
    assert list(etc.glob(".learnlab-hostid.*")) == []


@pytest.mark.parametrize(
    "identity",
    ["", "0" * 31, "g" * 32, "1" * 33, "1" * 32 + "\n\n", "1" * 32 + "\x00"],
)
def test_hostid_rejects_invalid_machine_id_without_partial_target(
    hostid_sandbox, identity
):
    etc, run = hostid_sandbox
    (etc / "machine-id").write_text(identity)
    assert run().returncode != 0
    assert not (etc / "hostid").exists()
    assert list(etc.glob(".learnlab-hostid.*")) == []


@pytest.mark.parametrize(
    "failure", ["chown", "mv", "owner", "symlink", "hardlink", "writable-parent"]
)
def test_hostid_fails_closed_on_unsafe_layout_or_write_failure(hostid_sandbox, failure):
    etc, run = hostid_sandbox
    machine_id = etc / "machine-id"
    machine_id.write_text("1234abcd" + "0" * 24 + "\n")
    if failure == "symlink":
        machine_id.rename(etc / "original")
        machine_id.symlink_to(etc / "original")
    elif failure == "hardlink":
        (etc / "other-link").hardlink_to(machine_id)
    elif failure == "writable-parent":
        etc.chmod(0o777)
    result = run(TEST_FAIL=failure, TEST_OWNER="1001" if failure == "owner" else "0")
    assert result.returncode != 0
    assert not (etc / "hostid").exists()
    assert list(etc.glob(".learnlab-hostid.*")) == []


@pytest.mark.parametrize("layout", ["dangling-symlink", "directory"])
def test_hostid_never_replaces_an_unexpected_target(hostid_sandbox, layout):
    etc, run = hostid_sandbox
    (etc / "machine-id").write_text("1234abcd" + "0" * 24 + "\n")
    target = etc / "hostid"
    if layout == "dangling-symlink":
        target.symlink_to(etc / "missing")
    else:
        target.mkdir()
    assert run().returncode != 0
    assert target.is_symlink() if layout == "dangling-symlink" else target.is_dir()
    assert list(etc.glob(".learnlab-hostid.*")) == []


def assert_ordered(text, *actions):
    offset = 0
    for action in actions:
        found = text.find(action, offset)
        assert found >= 0, f"Missing/out-of-order operator action: {action}"
        offset = found + len(action)


def test_post_install_requires_stopped_vm_before_boot_order_change():
    text = lesson_text("install-nixos")
    assert_ordered(
        text,
        "nixos-install` interactively",
        "passwd lab",
        "poweroff`",
        "status: stopped",
        "SCSI disk first",
        "Start",
        "findmnt /`",
    )
    assert "before ISO/network" in text
    assert "keep the ISO attached as recovery media" in text


def test_hostid_boot_ordering_and_seal_phase_preserve_both_identity_boundaries():
    install = lesson_text("install-nixos")
    for contract in (
        "networking.hostId = null;",
        'ConditionPathExists = "!/etc/hostid"',
        'after = [ "systemd-machine-id-commit.service" "local-fs.target" ]',
        'before = [ "multi-user.target" ]',
        'wantedBy = [ "multi-user.target" ]',
        'Type = "oneshot"',
        "ext4",
        "ZFS",
        "early-boot",
    ):
        assert contract in install
    access = lesson_text("configure-lab-access")
    assert_ordered(
        access,
        "nixos-rebuild test",
        "systemctl is-enabled learnlab-hostid.service",
        "ExecMainStatus",
        "hostid)",
        "head -c 8 /etc/machine-id",
    )
    seal = lesson_text("seal-and-convert")
    assert_ordered(
        seal,
        "nixos-option networking.hostId",
        "sudo pgrep -a -x sshd",
        "sudo truncate -s 0 /etc/machine-id",
        "sudo rm -i -- /etc/hostid",
        "for each configured host-key pair",
        "/etc/hostid is absent",
        "sudo systemctl poweroff",
    )


def test_two_clones_compare_hostid_before_and_after_reboot():
    text = lesson_text("test-two-clones")
    assert_ordered(
        text,
        "hostid)",
        "head -c 8 /etc/machine-id",
        "host IDs must differ",
        "sudo systemctl reboot",
        "machine ID, host ID",
        "stored pre-rebuild/reboot baseline",
    )
    assert "four-byte" in text


def test_bootstrap_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
    assert course.lessons[0].id == "prerequisites-and-safety"
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        assert policy.scope is EnvironmentScope.NONE
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
        for step in lesson.steps:
            assert step.verifications
            assert all(
                v.type
                in {
                    VerificationType.TEXT_EVIDENCE,
                    VerificationType.MANUAL_CONFIRMATION,
                }
                for v in step.verifications
            )


def test_bootstrap_validates_without_findings():
    report = validate_catalog(CurriculumCatalog(ROOT), COURSE_PATH)
    assert report.ok
    assert report.findings == ()


def test_complete_lesson_order_and_handoff():
    assert [lesson.id for lesson in load_course().lessons] == [
        "prerequisites-and-safety",
        "create-installer-vm",
        "install-nixos",
        "configure-lab-access",
        "seal-and-convert",
        "test-two-clones",
        "configure-provider",
    ]
    handoff = lesson_text("configure-provider")
    for concept in (
        'learnlab provider test "$PROFILE"',
        'learnlab validate nginx-nixos/nginx-basics --provider "$PROFILE"',
        'learnlab validate nftables-nixos/nftables-basics --provider "$PROFILE"',
        'learnlab validate systemd-nixos/service-authoring --provider "$PROFILE"',
        "template_capabilities",
        "default_provider",
        "token_secret_env",
        "learner-owned",
        "Do not use learnlab destroy",
        "absence",
        "VMID alone",
        "retain the template",
        "source",
        "clone permissions",
    ):
        assert concept in handoff


def test_provider_bootstrap_cross_link_is_optional_and_keeps_none_scope():
    text = lesson_text("configure-provider")
    assert "proxmox/provider-bootstrap" in text
    assert "optional" in text.lower()
    assert "direct advanced setup" in text.lower()
    assert "not a prerequisite" in text.lower()
    policy = load_course().effective_environment(
        next(item for item in load_course().lessons if item.id == "configure-provider")
    )
    assert policy.scope is EnvironmentScope.NONE
    assert policy.provider_capability is None


def test_installer_teaches_target_specific_steps():
    text = lesson_text("install-nixos")
    for concept in [
        "nixos-generate-config",
        "nixos-install",
        "hardware-configuration.nix",
        "system.stateVersion",
    ]:
        assert concept.lower() in text.lower()
    assert "Installer console" in text
    assert "disk" in text.lower() and "confirm" in text.lower()


def test_access_covers_required_guest_configuration():
    text = lesson_text("configure-lab-access")
    for concept in [
        "services.qemuGuest.enable",
        "services.openssh.enable",
        "environment.systemPackages",
        "nixos-rebuild test",
    ]:
        assert concept in text
    assert "private key" in text.lower()
    assert "public key" in text.lower()


def test_installer_vm_teaches_media_and_boot_boundary():
    text = lesson_text("create-installer-vm")
    for concept in [
        "HTTPS",
        "SHA-256",
        "26.05",
        "x86_64",
        "Q35",
        "OVMF",
        "Secure Boot",
        "DHCP",
    ]:
        assert concept in text


def test_sealing_and_clone_identity_contract():
    seal = lesson_text("seal-and-convert").lower()
    clones = lesson_text("test-two-clones").lower()
    assert "snapshot" in seal and "console" in seal
    assert "do not reboot" in seal
    assert "/etc/machine-id" in seal
    assert "/var/lib/dbus/machine-id" in seal
    assert "two" in clones and "full clones" in clones
    assert "distinct" in clones and "stable" in clones
    assert "known_hosts" in clones
    assert "ssh-keyscan alone" in clones


@pytest.mark.parametrize(
    "concepts",
    [
        ("findmnt", "symlink", "regular file", "read-only", "D-Bus fallback"),
        (
            "services.openssh.hostKeys",
            "sshd.service",
            "ExecStartPre",
            "generateHostKeys",
        ),
        ("systemd.machine_id", "firmware", "MAC", "snapshot"),
        ("already a template", "interruption", "another profile", "VMID alone"),
    ],
)
def test_sealing_retains_os_specific_stop_conditions(concepts):
    text = lesson_text("seal-and-convert")
    for concept in concepts:
        assert concept.lower() in text.lower()
    assert "rm -rf" not in text
    assert "ssh_host_*" not in text


def test_clone_acceptance_requires_nixos_rebuild_and_console_trust():
    text = lesson_text("test-two-clones").lower()
    for concept in (
        "nixos-rebuild",
        "console",
        "strictHostKeyChecking=yes".lower(),
        "sudo -n true",
        "disk-only",
        "reboot",
        "pass/fail",
        "failed lookup",
        "fresh console-verified reenrollment",
        "machine-id",
        "full clones",
    ):
        assert concept in text


def test_access_trust_state_loss_requires_console_reenrollment():
    text = lesson_text("configure-lab-access").lower()
    guide = (Path(__file__).parents[1] / "docs/NixOS-Template-Guide.md").read_text()
    assert "fresh console-verified reenrollment" in text
    assert "fresh console-verified reenrollment" in guide.lower()


@pytest.mark.parametrize("source", ["seal-and-convert", "guide"])
def test_guest_poweroff_requires_stopped_state_without_assuming_management_task(source):
    if source == "guide":
        text = (Path(__file__).parents[1] / "docs/NixOS-Template-Guide.md").read_text()
    else:
        text = lesson_text(source)
    assert "positively verify Stopped" in text
    assert "only if an actual management shutdown task was initiated" in text


@pytest.mark.parametrize("source", ["seal-and-convert", "guide"])
def test_sealing_checks_established_ssh_sessions_and_processes(source):
    if source == "guide":
        text = (Path(__file__).parents[1] / "docs/NixOS-Template-Guide.md").read_text()
    else:
        text = lesson_text(source)
    lower = text.lower()

    assert "every effective ssh port" in lower
    assert "before stopping" in lower and "sshd -t" in lower
    assert "listening sockets alone" in lower
    assert "state established" in lower
    assert "pgrep -a -x sshd" in lower
    assert "no output" in lower
    assert "permission" in lower and "stop" in lower


@pytest.mark.parametrize("source", ["configure-lab-access", "test-two-clones", "guide"])
def test_fresh_ssh_acceptance_disables_connection_sharing(source):
    if source == "guide":
        text = (Path(__file__).parents[1] / "docs/NixOS-Template-Guide.md").read_text()
    else:
        text = lesson_text(source)
    commands = [
        line.strip() for line in text.splitlines() if line.strip().startswith("ssh -i ")
    ]
    assert commands, f"Missing fresh SSH acceptance example in {source}"
    for command in commands:
        assert "-o ControlPath=none" in command


@pytest.mark.parametrize(
    ("lesson_id", "check_id", "accepted", "rejected"),
    [
        ("create-installer-vm", "media-integrity", "checksum", "skip checksum"),
        ("install-nixos", "install-state-version", "26.05", "latest"),
        ("configure-lab-access", "key-material", "public key", "private key"),
        ("seal-and-convert", "sealed-next-action", "power off", "reboot"),
        ("test-two-clones", "clone-identity-rule", "distinct and stable", "same"),
        ("configure-provider", "handoff-certification", "self-attested", "certified"),
    ],
)
def test_added_knowledge_checks_execute_exact_answer_contract(
    lesson_id,
    check_id,
    accepted,
    rejected,
):
    from learnlab.validation import TextEvidenceValidator, ValidationContext

    class AnswerPrompt:
        def __init__(self, answer):
            self.answer = answer

        def ask_text(self, prompt):
            return self.answer

    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    checks = {
        check.id: check
        for step in lesson.steps
        for check in step.verifications
        if check.type is VerificationType.TEXT_EVIDENCE
    }
    assert set(checks) == {check_id}
    check = checks[check_id]
    for answer, expected in [
        (accepted, True),
        (rejected, False),
        ("", False),
        ("unrelated", False),
    ]:
        result = TextEvidenceValidator().validate(
            ValidationContext(prompt=AnswerPrompt(answer)),
            check,
        )
        assert result.passed is expected
