from pathlib import Path

from learnlab.course_certification import CourseMaturity
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/provider-bootstrap"


def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)


def lesson_text(lesson_id: str) -> str:
    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    return "\n".join(step.instructions for step in lesson.steps)


def all_course_text() -> str:
    return "\n".join(lesson_text(lesson.id) for lesson in load_course().lessons)


def test_initial_bootstrap_slice_is_draft_and_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
    assert [lesson.id for lesson in course.lessons] == [
        "safety-and-private-worksheet",
        "read-only-inventory",
    ]
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        assert policy.scope is EnvironmentScope.NONE
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
        assert all(
            check.type
            in {
                VerificationType.TEXT_EVIDENCE,
                VerificationType.MANUAL_CONFIRMATION,
            }
            for step in lesson.steps
            for check in step.verifications
        )


def test_inventory_is_private_read_only_and_fails_closed():
    text = lesson_text("read-only-inventory")
    for fragment in (
        "installed PVE version",
        "command help",
        "source template",
        "storage",
        "network",
        "users",
        "tokens",
        "roles",
        "ACLs",
        "collision",
        "403",
        "filtered",
        "stop",
    ):
        assert fragment in text
