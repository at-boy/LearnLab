from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from learnlab.curriculum import CurriculumCatalog, CurriculumError


@pytest.fixture
def collections_dir() -> Path:
    return Path(__file__).parents[1] / "collections"


@pytest.fixture
def course(collections_dir: Path):
    return CurriculumCatalog(collections_dir).load_course("proxmox/proxmox-admin")


def test_loads_explicit_platform_hierarchy(collections_dir: Path):
    course = CurriculumCatalog(collections_dir).load_course("proxmox/proxmox-admin")

    assert course.collection_id == "proxmox"
    assert course.id == "proxmox-admin"
    assert [lesson.id for lesson in course.lessons] == ["api-access", "api-tokens"]
    assert [step.id for step in course.lessons[0].steps] == [
        "understand-api",
        "locate-endpoint",
    ]


def test_first_incomplete_follows_course_order(course):
    assert course.first_incomplete({"api-access"}).id == "api-tokens"


@pytest.mark.parametrize("invalid_path", ["proxmox", "a/b/c", "/proxmox-admin"])
def test_course_path_requires_collection_slash_course(
    invalid_path: str, collections_dir: Path
):
    with pytest.raises(CurriculumError, match="collection/course"):
        CurriculumCatalog(collections_dir).load_course(invalid_path)


def test_curriculum_contains_no_provider_configuration_or_secret_material(
    collections_dir: Path,
):
    prohibited_text = {"token_secret", "PVEAPIToken=", "private-value"}
    prohibited_keys = {
        "template_vmid",
        "node",
        "storage",
        "network",
        "api_url",
        "provider_profile",
    }

    for path in collections_dir.rglob("*.yaml"):
        source = path.read_text(encoding="utf-8")
        assert not any(value in source for value in prohibited_text)
        parsed = yaml.safe_load(source)
        assert isinstance(parsed, dict)
        assert prohibited_keys.isdisjoint(parsed)
