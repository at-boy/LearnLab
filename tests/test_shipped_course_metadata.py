"""Characterize shipped metadata without operating a provider or guest."""

from pathlib import Path

import pytest

from learnlab.course_certification import CourseMaturity
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
PENDING = (
    "nginx/nginx-basics",
    "nginx-nixos/nginx-basics",
    "nftables-debian13/nftables-basics",
    "nftables-nixos/nftables-basics",
    "systemd-debian/service-authoring",
    "systemd-nixos/service-authoring",
)
COURSE_PATHS = tuple(
    f"{path.parents[2].name}/{path.parent.name}"
    for path in sorted(ROOT.glob("*/courses/*/course.yaml"))
)


@pytest.mark.parametrize("course_path", COURSE_PATHS)
def test_every_shipped_course_loads_with_metadata(course_path: str) -> None:
    catalog = CurriculumCatalog(ROOT)
    course = catalog.load_course(course_path)
    summary = next(item for item in catalog.list_courses() if item.path == course_path)
    assert isinstance(course.maturity, CourseMaturity)
    assert summary.maturity is course.maturity
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        if policy.scope is EnvironmentScope.NONE:
            assert policy.provider_capability is None
            assert policy.guest_capabilities == ()
        else:
            assert policy.guest_capabilities
            assert len(set(policy.guest_capabilities)) == len(
                policy.guest_capabilities
            )


def test_exact_pending_courses_ship_as_drafts() -> None:
    pending_families = {
        "nginx",
        "nginx-nixos",
        "nftables-debian13",
        "nftables-nixos",
        "systemd-debian",
        "systemd-nixos",
    }
    assert {
        path for path in COURSE_PATHS if path.split("/")[0] in pending_families
    } == set(PENDING)
    catalog = CurriculumCatalog(ROOT)
    assert len(PENDING) == 6
    for path in PENDING:
        assert catalog.load_course(path).maturity is CourseMaturity.DRAFT
