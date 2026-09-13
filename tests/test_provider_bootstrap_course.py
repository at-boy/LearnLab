import re
from pathlib import Path

import pytest

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


def test_bootstrap_is_draft_and_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
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


def test_complete_lesson_order():
    assert [lesson.id for lesson in load_course().lessons] == [
        "safety-and-private-worksheet",
        "read-only-inventory",
        "map-provider-authority",
        "create-identity-roles-and-acls",
        "add-named-profile",
        "run-get-only-health",
        "authorize-scratch-lifecycle",
        "reconcile-and-rollback",
    ]


def test_readme_distinguishes_provider_and_template_bootstrap_paths():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    for fragment in (
        "proxmox/provider-bootstrap",
        "proxmox/nixos-template",
        "proxmox/proxmox-admin",
        "optional",
        "provider-backed",
        "learnlab start proxmox/provider-bootstrap --include-drafts",
        "self-attestation",
        "not live certification",
    ):
        assert fragment in readme


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


def test_profile_edit_branches_create_new_default_and_preserve_existing_defaults():
    steps = {step.id: step.instructions for step in lesson_steps("add-named-profile")}
    backup_branch = steps["back-up-config"]
    profile_example = steps["add-unused-profile"]
    new_default = 'default_provider = "CHOSEN_PROFILE"'
    provider_table = '[providers."CHOSEN_PROFILE"]'

    assert new_default in profile_example
    assert profile_example.index(new_default) < profile_example.index(provider_table)
    assert "For a genuinely new configuration" in backup_branch
    assert "For an existing configuration" in backup_branch
    assert "preserve every existing default exactly" in backup_branch


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


def test_scratch_compatibility_validation_has_an_exact_nonblocking_warning_set():
    text = lesson_text("run-get-only-health")
    warning_baseline = next(
        line for line in text.splitlines() if "exactly three warning findings" in line
    )

    assert 'COURSE="proxmox/proxmox-admin"' in text
    assert 'learnlab validate "$COURSE" --provider "$PROFILE" --format json' in text
    assert '"ok": true' in text
    assert re.findall(r"`([^`]+)`", warning_baseline) == [
        '"ok": true',
        "deprecated-requirements",
        "missing-os-capability",
        "manual-confirmation-with-objective-check",
    ]
    assert "acknowledged and nonblocking" in text
    assert "changed, new, or unexpected finding" in text
    assert "separate explicit live authorization remains required" in text
    assert "any finding" not in text.lower()


def test_profile_and_health_lessons_reinspect_before_resume():
    profile = lesson_text("add-named-profile")
    health = lesson_text("run-get-only-health")

    for fragment in (
        "Resume/reinspection: after any interruption",
        "partially edited table",
        "owner-only backup",
        "private absent-config before-state",
        "do not blindly re-add",
    ):
        assert fragment in profile
    for fragment in (
        "Resume/reinspection: after any interruption",
        "recheck the selected profile",
        "TLS verification",
        "effective user/token authority",
        "securely repopulate the process secret environment",
        "before repeating",
    ):
        assert fragment in health


def test_profile_before_state_supports_existing_and_genuinely_new_configs():
    text = lesson_text("add-named-profile")
    for fragment in (
        "positively verify that the configuration is absent",
        "record the private absent-config before-state",
        "create the configuration owner-only",
        "genuinely new configuration",
    ):
        assert fragment in text

    check = next(
        check
        for step in lesson_steps("add-named-profile")
        for check in step.verifications
        if check.id == "profile-backup-self-attestation"
    )
    assert check.type is VerificationType.MANUAL_CONFIRMATION
    assert check.prompt is not None
    assert "verified owner-only backup" in check.prompt
    assert "verified absence before creation" in check.prompt


def test_health_four_gets_are_the_complete_successful_path():
    text = lesson_text("run-get-only-health")
    assert "complete successful health path makes four GET requests" in text
    assert "If GET /version fails, health returns early" in text
    assert "a failed health run can issue fewer than four requests" in text
    assert "The health check makes exactly four GET requests" not in text


def test_capability_findings_are_independent_of_health_success():
    text = lesson_text("run-get-only-health")
    assert "Capability comparison is independent of health success" in text
    assert "health failures can coexist with capability findings" in text
    assert "does not prove guest execution or mutation" in text
    assert "only when health permits" not in text


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


def test_live_protocol_is_separate_isolated_and_fail_closed():
    text = lesson_text("authorize-scratch-lifecycle")
    for fragment in (
        "separate explicit authorization",
        "scratch profile",
        "isolated",
        "XDG",
        "empty",
        "proxmox/proxmox-admin",
        '--provider "$PROFILE"',
        "--include-drafts",
        "owner-only backup",
        "preserve-progress",
        "erase-progress",
        "filtered inventory",
        "uncertain",
        "do not retry",
    ):
        assert fragment in text


def test_cleanup_precedes_revocation_and_keeps_recovery_evidence():
    text = lesson_text("reconcile-and-rollback")
    for fragment in (
        "completed delete task",
        "authorized refreshed inventory",
        "attached scratch storage",
        "source template still present",
        "independent administrator",
        "protected state backup",
        "Retain",
        "Revoke",
        "token first",
        "reverse order",
        "unexpected reference",
        "course remains draft",
    ):
        assert fragment in text


@pytest.mark.parametrize(
    ("lesson_id", "check_id", "accepted", "rejected"),
    [
        (
            "safety-and-private-worksheet",
            "course-operation-boundary",
            "learner-operated",
            "automated",
        ),
        ("read-only-inventory", "inventory-mode", "read-only inventory", "mutation"),
        (
            "map-provider-authority",
            "permission-proof",
            "installed and live",
            "built-in role",
        ),
        (
            "create-identity-roles-and-acls",
            "token-authority",
            "intersection",
            "user only",
        ),
        (
            "add-named-profile",
            "secret-storage",
            "environment-variable name",
            "secret value",
        ),
        (
            "run-get-only-health",
            "health-proof",
            "GET-only observation",
            "lifecycle authorized",
        ),
        (
            "authorize-scratch-lifecycle",
            "authorization-scope",
            "one approved scratch lifecycle",
            "general permission",
        ),
        (
            "reconcile-and-rollback",
            "progress-kind",
            "self-attested progress",
            "certified",
        ),
    ],
)
def test_knowledge_checks_execute_exact_answer_contract(
    lesson_id, check_id, accepted, rejected
):
    class AnswerPrompt:
        def __init__(self, answer):
            self.answer = answer

        def ask_text(self, prompt):
            return self.answer

    from learnlab.validation import TextEvidenceValidator, ValidationContext

    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    checks = {
        check.id: check
        for step in lesson.steps
        for check in step.verifications
        if check.type is VerificationType.TEXT_EVIDENCE
    }
    assert set(checks) == {check_id}
    for answer, expected in (
        (accepted, True),
        (rejected, False),
        ("", False),
        ("unrelated", False),
    ):
        result = TextEvidenceValidator().validate(
            ValidationContext(prompt=AnswerPrompt(answer)), checks[check_id]
        )
        assert result.passed is expected


def test_course_has_no_unfinished_or_live_deployment_values():
    text = all_course_text()
    for forbidden in (
        "T" + "ODO",
        "T" + "BD",
        "192.168.",
        "pve02",
        "learnlab@pve",
        "!provider",
        "vm-103",
        "local-lvm",
        "local-ssd",
    ):
        assert forbidden not in text
    assert not re.search(r"https?://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?", text)
    assert not re.search(
        r"(?i)\b(?:vmid|template_vmid)\s*(?:=|:)\s*[1-9]\d{2,8}\b", text
    )


def test_lifecycle_and_cleanup_lessons_keep_step_contracts():
    expected_steps = {
        "authorize-scratch-lifecycle": [
            "request-live-authorization",
            "prepare-isolated-state",
            "run-one-managed-environment",
            "back-up-before-destroy",
        ],
        "reconcile-and-rollback": [
            "prove-positive-cleanup",
            "obtain-independent-confirmation",
            "choose-retain-or-revoke",
            "separate-progress-from-certification",
        ],
    }
    for lesson_id, step_ids in expected_steps.items():
        assert [step.id for step in lesson_steps(lesson_id)] == step_ids


def test_scratch_protocol_preserves_lifecycle_request_order():
    text = lesson_text("authorize-scratch-lifecycle")
    operations = (
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
    positions = [text.index(operation) for operation in operations]
    assert positions == sorted(positions)
