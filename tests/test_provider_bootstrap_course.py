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


def lesson_steps(lesson_id: str):
    return next(item for item in load_course().lessons if item.id == lesson_id).steps


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


def test_introductory_lessons_keep_stable_steps_checks_and_execution_locations():
    expected_steps = {
        "safety-and-private-worksheet": {
            "establish-boundary": ("course-operation-boundary",),
            "prepare-private-worksheet": ("private-worksheet-self-attestation",),
            "confirm-resume-rules": ("resume-reinspection-self-attestation",),
        },
        "read-only-inventory": {
            "inspect-installed-version": ("installed-guidance-self-attestation",),
            "inventory-resources": ("inventory-mode",),
            "inventory-access-objects": ("access-inventory-self-attestation",),
        },
    }
    expected_prefixes = {
        "safety-and-private-worksheet": "Controller:",
        "read-only-inventory": "Proxmox node:",
    }

    for lesson_id, expected in expected_steps.items():
        steps = lesson_steps(lesson_id)
        assert {
            step.id: tuple(check.id for check in step.verifications) for step in steps
        } == expected
        assert all(
            line.startswith(expected_prefixes[lesson_id])
            for step in steps
            for line in step.instructions.splitlines()
            if line
        )
        assert all(
            not {check.type for check in step.verifications}
            >= {
                VerificationType.TEXT_EVIDENCE,
                VerificationType.MANUAL_CONFIRMATION,
            }
            for step in steps
        )

    checks = {
        check.id: check
        for lesson_id in expected_steps
        for step in lesson_steps(lesson_id)
        for check in step.verifications
    }
    assert checks["course-operation-boundary"].equals == "learner-operated"
    assert checks["inventory-mode"].equals == "read-only inventory"


def test_introductory_lessons_require_prerequisite_and_reinspection_on_resume():
    safety = lesson_text("safety-and-private-worksheet")
    inventory = lesson_text("read-only-inventory")

    assert "existing human administrator has authority" in safety
    assert "After any interruption" in safety
    assert (
        "confirm the private worksheet and existing human administrator authority"
        in inventory
    )
    assert "After any interruption, reinspect" in inventory


def test_private_worksheet_attestation_keeps_non_secret_identifiers_private():
    worksheet = lesson_text("safety-and-private-worksheet")
    checks = {
        check.id: check
        for step in lesson_steps("safety-and-private-worksheet")
        for check in step.verifications
    }

    assert (
        "Record only non-secret local identifiers needed for reconciliation"
        in worksheet
    )
    assert (
        "No worksheet value or inventory output is pasted into LearnLab." in worksheet
    )
    prompt = checks["private-worksheet-self-attestation"].prompt
    assert prompt is not None
    assert "contains no secrets" in prompt
    assert (
        "private worksheet values or inventory output were not pasted into LearnLab"
        in prompt
    )
