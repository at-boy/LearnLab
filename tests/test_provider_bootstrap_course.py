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
        "map-provider-authority",
        "create-identity-roles-and-acls",
        "add-named-profile",
        "run-get-only-health",
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
    checks = {
        check.id: check
        for lesson_id in expected_steps
        for step in lesson_steps(lesson_id)
        for check in step.verifications
    }
    assert checks["course-operation-boundary"].equals == "learner-operated"
    assert checks["inventory-mode"].equals == "read-only inventory"


def test_introductory_verification_types_separate_answers_and_self_attestations():
    checks = {
        check.id: check
        for lesson in load_course().lessons
        for step in lesson.steps
        for check in step.verifications
    }

    assert {
        check_id: checks[check_id].type
        for check_id in ("course-operation-boundary", "inventory-mode")
    } == {
        "course-operation-boundary": VerificationType.TEXT_EVIDENCE,
        "inventory-mode": VerificationType.TEXT_EVIDENCE,
    }
    assert {
        check_id: checks[check_id].type
        for check_id in (
            "private-worksheet-self-attestation",
            "resume-reinspection-self-attestation",
            "installed-guidance-self-attestation",
            "access-inventory-self-attestation",
        )
    } == {
        "private-worksheet-self-attestation": VerificationType.MANUAL_CONFIRMATION,
        "resume-reinspection-self-attestation": VerificationType.MANUAL_CONFIRMATION,
        "installed-guidance-self-attestation": VerificationType.MANUAL_CONFIRMATION,
        "access-inventory-self-attestation": VerificationType.MANUAL_CONFIRMATION,
    }


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


def test_permission_design_preserves_global_vms_limit_and_actor_separation():
    text = lesson_text("map-provider-authority")
    for fragment in (
        "installed-version/live-confirmation-required",
        "bootstrap administrator",
        "template builder",
        "validation-only caller",
        "runtime user",
        "privilege-separated token",
        "intersection",
        "propagated ACL at /vms",
        "cluster-global VMID",
        "no pool",
        "broader",
        "source template",
        "target VM",
        "storage",
        "network",
        "node",
        "guest agent",
        "VM.GuestAgent.FileRead",
        "VM.GuestAgent.FileWrite",
        "VM.GuestAgent.FileSystemMgmt",
        "VM.GuestAgent.Unrestricted",
    ):
        assert fragment in text


def test_acl_setup_forbids_broad_fallback_and_requires_reconciliation():
    text = lesson_text("create-identity-roles-and-acls")
    for fragment in (
        "privsep=1",
        "PVEAuditor",
        "PVEVMAdmin",
        "Administrator",
        "Datastore.Allocate",
        "Datastore.AllocateSpace",
        "Datastore.AllocateTemplate",
        "Datastore.Audit",
        "403",
        "filtered",
        "propagate",
        "effective permissions",
        "reverse order",
    ):
        assert fragment in text
    assert "Do not assign Administrator" in text
    assert "Do not add Datastore.Allocate" in text


def test_named_profile_is_additive_secret_free_and_tls_verified():
    text = lesson_text("add-named-profile")
    for field in (
        "type",
        "api_url",
        "token_id",
        "token_secret_env",
        "template_vmid",
        "template_name",
        "node",
        "storage",
        "network",
        "ssh_user",
        "ssh_identity_file",
        "tls_verify",
        "template_capabilities",
    ):
        assert field in text
    for fragment in (
        "preserve every existing provider",
        "preserve existing default_provider",
        "external hidden shell read",
        "LearnLab resolves only the environment variable",
        "tls_verify = true",
        "shell tracing",
        "unset",
    ):
        assert fragment in text


def test_health_lesson_distinguishes_observation_from_mutation_proof():
    text = lesson_text("run-get-only-health")
    assert 'learnlab provider test "$PROFILE"' in text
    assert 'learnlab validate "$COURSE" --provider "$PROFILE"' in text
    for fragment in (
        "four GET requests",
        "necessary but not sufficient",
        "storage",
        "network",
        "inferred",
        "403",
        "do not broaden",
        "does not certify",
    ):
        assert fragment in text


def test_profile_and_health_lessons_keep_step_and_concept_answer_contracts():
    expected_steps = {
        "add-named-profile": [
            "back-up-config",
            "add-unused-profile",
            "supply-secret-externally",
            "inspect-without-copying",
        ],
        "run-get-only-health": [
            "select-profile",
            "run-provider-health",
            "run-provider-aware-validation",
            "interpret-failures",
        ],
    }
    for lesson_id, step_ids in expected_steps.items():
        assert [step.id for step in lesson_steps(lesson_id)] == step_ids
    checks = {
        check.id: check
        for lesson_id in expected_steps
        for step in lesson_steps(lesson_id)
        for check in step.verifications
    }
    for check_id, answer in (
        ("secret-storage", "environment-variable name"),
        ("health-proof", "GET-only observation"),
    ):
        assert checks[check_id].type is VerificationType.TEXT_EVIDENCE
        assert checks[check_id].equals == answer


def test_provider_authority_names_every_current_request_and_limit():
    text = lesson_text("map-provider-authority")
    ordered_operations = (
        "GET /version",
        "GET /nodes",
        "GET /cluster/resources?type=vm",
        "GET /nodes/{node}/qemu/{template_vmid}/config",
        "GET /cluster/nextid",
        "POST /nodes/{profile_node}/qemu/{template_vmid}/clone",
        "clone task wait: GET /nodes/{node}/tasks/{upid}/status",
        "post-clone locate: GET /cluster/resources?type=vm",
        "POST /nodes/{node}/qemu/{vmid}/status/start",
        "start task wait: GET /nodes/{node}/tasks/{upid}/status",
        "POST /nodes/{node}/qemu/{vmid}/agent/ping",
        "GET /nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
        "cleanup preflight locate: GET /cluster/resources?type=vm",
        "POST /nodes/{node}/qemu/{vmid}/status/stop",
        "stop task wait: GET /nodes/{node}/tasks/{upid}/status",
        "DELETE /nodes/{node}/qemu/{vmid}",
        "delete task wait: GET /nodes/{node}/tasks/{upid}/status",
        "final locate: GET /cluster/resources?type=vm",
    )
    positions = [text.index(fragment) for fragment in ordered_operations]
    assert positions == sorted(positions)
    for fragment in (
        "newid",
        "generated name",
        "full=1",
        "configured storage",
        "semantically read-only",
        "does not compare the returned node",
        "no pool",
    ):
        assert fragment in text

    for check_id in (
        "api-reachable",
        "template-visible",
        "vm-running",
        "guest-agent-ready",
    ):
        assert check_id in text

    for privilege in (
        "Sys.Audit",
        "VM.Audit",
        "VM.Clone",
        "VM.Allocate",
        "Datastore.AllocateSpace",
        "Datastore.Audit",
        "SDN.Use",
        "SDN.Audit",
        "VM.PowerMgmt",
        "VM.GuestAgent.Audit",
    ):
        matching_rows = [line for line in text.splitlines() if privilege in line]
        assert matching_rows, privilege
        assert all(
            "installed-version/live-confirmation-required" in line
            for line in matching_rows
        ), privilege


def test_authority_lessons_keep_step_and_concept_answer_contracts():
    expected_steps = {
        "map-provider-authority": [
            "map-health-surface",
            "separate-actors",
            "map-resource-scopes",
            "accept-current-vms-limit",
        ],
        "create-identity-roles-and-acls": [
            "inventory-before-change",
            "create-dedicated-identities",
            "create-custom-roles",
            "apply-acls-one-scope-at-a-time",
            "reconcile-effective-authority",
        ],
    }
    for lesson_id, step_ids in expected_steps.items():
        assert [step.id for step in lesson_steps(lesson_id)] == step_ids
    checks = {
        check.id: check
        for lesson_id in expected_steps
        for step in lesson_steps(lesson_id)
        for check in step.verifications
    }
    for check_id, answer in (
        ("permission-proof", "installed and live"),
        ("token-authority", "intersection"),
    ):
        assert checks[check_id].type is VerificationType.TEXT_EVIDENCE
        assert checks[check_id].equals == answer
    assert all(
        check.prompt is not None and check.prompt.startswith("Self-attestation:")
        for check in checks.values()
        if check.type is VerificationType.MANUAL_CONFIRMATION
    )
