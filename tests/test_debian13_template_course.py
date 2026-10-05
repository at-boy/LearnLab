"""Exercise the packaged Debian template bootstrap boundary."""

from pathlib import Path

from learnlab.course_certification import CourseMaturity
from learnlab.course_validation import validate_catalog
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType
from learnlab.validation import TextEvidenceValidator, ValidationContext

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/debian13-template"


def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)


def lesson_text(lesson_id):
    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
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


def test_installation_sequence_is_exposed_by_catalog():
    assert [lesson.id for lesson in load_course().lessons] == [
        "prerequisites-and-safety",
        "create-installer-vm",
        "install-debian13",
        "configure-lab-access",
        "seal-and-convert",
        "test-two-clones",
        "configure-provider",
    ]


def test_provider_handoff_records_self_attestation_and_stays_none_scoped():
    course = load_course()
    lesson = course.lessons[-1]
    assert lesson.id == "configure-provider"
    assert course.effective_environment(lesson).scope is EnvironmentScope.NONE
    assert [step.id for step in lesson.steps] == [
        "create-profile",
        "check-provider-read-only",
        "reconcile-test-clones",
        "distinguish-completion-from-certification",
    ]
    assert [check.type for step in lesson.steps for check in step.verifications] == [
        VerificationType.MANUAL_CONFIRMATION,
        VerificationType.MANUAL_CONFIRMATION,
        VerificationType.MANUAL_CONFIRMATION,
        VerificationType.TEXT_EVIDENCE,
    ]


class AnswerPrompt:
    def __init__(self, answer):
        self.answer = answer

    def ask_text(self, prompt):
        return self.answer


def test_new_knowledge_checks_accept_concepts_and_reject_wrong_answers():
    cases = [
        ("create-installer-vm", "media-integrity", "checksum", "skip checksum"),
        ("install-debian13", "target-release", "13", "12"),
        ("configure-lab-access", "ssh-key-material", "public key", "private key"),
        ("seal-and-convert", "empty-machine-id-first-boot", "no", "yes"),
        ("test-two-clones", "keyscan-trust", "no", "yes"),
    ]
    for lesson_id, check_id, accepted, rejected in cases:
        lesson = next(
            lesson for lesson in load_course().lessons if lesson.id == lesson_id
        )
        verification = next(
            check
            for step in lesson.steps
            for check in step.verifications
            if check.id == check_id
        )
        validator = TextEvidenceValidator()
        assert validator.validate(
            ValidationContext(prompt=AnswerPrompt(accepted)), verification
        ).passed
        assert not validator.validate(
            ValidationContext(prompt=AnswerPrompt(rejected)), verification
        ).passed


def test_sealing_and_clone_steps_have_separate_decision_checkpoints():
    lessons = {lesson.id: lesson for lesson in load_course().lessons}
    assert [step.id for step in lessons["seal-and-convert"].steps] == [
        "inspect-candidate", "configure-missing-host-keys", "first-boot-concept",
        "generalize-identities", "convert-inspected-candidate",
    ]
    assert [step.id for step in lessons["test-two-clones"].steps] == [
        "inspect-clone-targets", "create-and-boot-two-clones", "authenticate-clone-ssh",
        "compare-and-reboot-identities", "keyscan-concept",
    ]
