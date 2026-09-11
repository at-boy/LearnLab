from pathlib import Path

from learnlab.course_certification import CourseMaturity
from learnlab.course_validation import validate_catalog
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/nixos-template"


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
