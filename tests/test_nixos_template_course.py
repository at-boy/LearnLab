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


@pytest.mark.parametrize(
    ("lesson_id", "check_id", "accepted", "rejected"),
    [
        ("create-installer-vm", "media-integrity", "checksum", "skip checksum"),
        ("install-nixos", "install-state-version", "26.05", "latest"),
        ("configure-lab-access", "key-material", "public key", "private key"),
        ("seal-and-convert", "sealed-next-action", "power off", "reboot"),
        ("test-two-clones", "clone-identity-rule", "distinct and stable", "same"),
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
