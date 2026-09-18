# Proxmox provider bootstrap — offline acceptance and live blockers

Status: **draft; offline gate passed; live acceptance not performed**.
Recorded 2026-09-14. The filename follows the approved design date,
2026-09-11.
Tested content revision: `cea6086845980512aaf030725f191e3f65678021`

Documentation-only TLS guidance refresh: 2026-09-19. The current digest below
was recomputed after the focused course suite and offline validator passed; see
`.superpowers/sdd/2026-09-14-nixos-live-corrections/task-5-report.md`. No live
acceptance or certification-registry update was performed.

Course: `proxmox/provider-bootstrap`. This record covers repository inspection,
offline curriculum validation, and automated non-live tests only. No provider,
network, Proxmox, lifecycle, operator-shell, SSH, guest, resource, permission,
profile, or secret operation was performed for this report. No deployment
identifier or credential is recorded here.

## Exact course digest

`92efd4934b2584f75e0acbc6260b8d66873f74a0da11f318e832632f2d72fda2`

This exact course digest was computed from
`src/learnlab/collections/proxmox/courses/provider-bootstrap` after the current
documentation-only refresh. The original whole-feature spec, quality-review,
and complete post-review evidence remains recorded below. It was computed with:

```sh
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from learnlab.course_certification import course_digest

root = Path("src/learnlab/collections/proxmox/courses/provider-bootstrap")
print(course_digest(root))
PY
```

Any later change to the course manifest or lesson bytes makes this digest stale
and requires the complete offline gate and digest computation to be repeated.

## Offline verification

The following pre-report commands ran in the isolated
`template-bootstrap-course` worktree and exited 0:

```text
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py tests/test_course_authoring_docs.py tests/test_cli.py tests/test_packaging.py -q -k 'not offline_report_keeps_live_protocol_pending'
166 passed, 1 deselected in 7.07s

.venv/bin/learnlab validate proxmox/provider-bootstrap
Validation passed with no findings.

.venv/bin/learnlab validate proxmox/nixos-template
Validation passed with no findings.
```

The complete post-review gate also ran before the revision and digest were
captured. Every command exited 0:

```text
.venv/bin/python -m pytest -m 'not live' -q -k 'not offline_report_keeps_live_protocol_pending'
591 passed, 2 deselected in 36.78s

.venv/bin/ruff check .
All checks passed!

.venv/bin/mypy src
Success: no issues found in 17 source files

.venv/bin/learnlab validate proxmox/provider-bootstrap
Validation passed with no findings.

.venv/bin/learnlab validate proxmox/nixos-template
Validation passed with no findings.

.venv/bin/learnlab validate --format json
schema_version: 1; ok: true; three known warnings listed below

git diff --check
exit 0; no output
```

The two deselections were the opt-in live test and the intentionally missing
report test. The latter had first been added exactly as the digest-bound
regression and observed RED: its focused run failed with `FileNotFoundError`
because this report did not yet exist.

Catalog JSON retained exactly the unchanged pre-existing warnings for
`proxmox/proxmox-admin`; neither target course produced a finding:

| Code | Source | Meaning |
| --- | --- | --- |
| `deprecated-requirements` | existing admin course manifest | Legacy requirements should migrate to guest capabilities. |
| `missing-os-capability` | existing admin course manifest | Its VM environment does not declare an OS guest capability. |
| `manual-confirmation-with-objective-check` | existing admin course API-access lesson | A manual attestation duplicates an objective check. |

These warnings were neither hidden nor changed by the provider-bootstrap work.

The digest-bound report test and review-readiness checks then produced:

```text
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending -q
1 passed in 0.01s

git cat-file -e e1721f3d00f21fd478c9ff31380672ca7687c650^{commit}
exit 0; no output

git diff --check e1721f3d00f21fd478c9ff31380672ca7687c650..HEAD
git diff --check
git diff --cached --check
each exited 0; no output

exact committed-history/staged/unstaged/untracked allowlist
allowlist passed for 18 changed paths

new-course-and-report redaction/placeholder scan
exit 1; no matches (expected ripgrep no-match status)

added-existing-document-lines redaction/placeholder scan
exit 1; no matches (expected ripgrep no-match status)
```

The implementation base resolved to a commit. The allowlist names the manifest,
all eight expected lesson files, each approved existing integration path, this
report, and the report test individually. Exit status 2 would have been a scan
error; neither scan returned it.

## Course structure and zero-dependency boundary

The real catalog loaded eight lessons in this exact order:

1. `safety-and-private-worksheet`
2. `read-only-inventory`
3. `map-provider-authority`
4. `create-identity-roles-and-acls`
5. `add-named-profile`
6. `run-get-only-health`
7. `authorize-scratch-lifecycle`
8. `reconcile-and-rollback`

Every effective environment uses `EnvironmentScope.NONE`. There is no provider
capability or guest capability, and the only allowed verification types are
`text-evidence` and `manual-confirmation`. Knowledge answers and action
attestations are local progress, not objective provider checks or certification.

The focused source and single-build installed-wheel tests both exercised real
start, save, and resume behavior while tripwires rejected settings loading,
secret resolution, provider construction or requests, SSH construction or
execution, and network-client use. That zero-dependency test result is included
in the 166 passing focused tests above. Displayed operator commands remain text
outside the LearnLab dependency graph and were not executed.

## Code-derived provider coverage and limits

Repository inspection and tests bind the lesson matrix to the current adapter
and lifecycle. The successful health path is GET-only and covers these generic
API paths:

1. `GET /version`
2. `GET /nodes`
3. `GET /cluster/resources?type=vm`
4. `GET /nodes/{node}/qemu/{template_vmid}/config`

Those observations establish reachability, configured node visibility, source
template identity, and configuration-derived storage/network matching only. A
health failure can return early, so a failed run may issue fewer than four
requests. Even health success does not prove global next-ID access, clone,
task-status, power, guest-agent, address-discovery, deletion, storage-use, or
network-use authority. Permission-filtered output can look like absence.

The separately authorized lifecycle surface is also represented in call order:
global next-ID allocation; full clone from the configured source without a pool
parameter; task-status polling; cluster-resource reconciliation; start and its
task wait; semantically read-only guest-agent ping via HTTP POST; interface
discovery; cleanup preflight; optional stop and its wait; delete and its wait;
and a final resource lookup checking whether a matching row remains. A lookup
that returns no matching row does not independently prove resource absence or
adequate visibility: filtered inventory remains a blocker and requires
independent administrator reconciliation. Offline inspection proves that
code-derived sequence, not the installed Proxmox privilege mapping or live
behavior.

## Actors, candidate permissions, and accepted limitation

The course separates four actors:

- The authorized bootstrap administrator inspects installed privileges and
  creates or later reconciles access-control objects without receiving runtime
  credentials.
- The human template builder receives only action-specific template and storage
  authority through the separate operator workflow.
- The validation-only caller has auditing/read visibility for the configured
  health resources and no inferred mutation authority.
- The dedicated LearnLab runtime user and privilege-separated token receive only
  the live-confirmed intersection needed for the disposable lifecycle.

All version-sensitive privilege mappings are labeled
`installed-version/live-confirmation-required`. User grants alone do not prove
token authority, and token grants cannot exceed the user. Effective permissions
must therefore be inspected separately for the user and token. Broad
`Administrator`, `PVEAdmin`, or all-purpose role fallback is not accepted.

The current adapter uses a cluster-global next identifier and sends no pool in
its clone request. Before a target exists, a target-specific ACL cannot grant
its creation rights. The course consequently makes the accepted propagated `/vms`
limitation conspicuous: the runtime identity needs live-confirmed target
allocation/lifecycle authority inherited there. Dedicated identities, separate
source/target/storage/network/node/agent roles, leaf ACLs, isolated acceptance
state, and periodic review mitigate but do not remove that broader reach. Pool
support or narrower preallocation requires a separate provider design.

## PVE 9.2.11 development discovery — not portable proof

The following prior observations belong only to one development environment.
They motivated inspection-first teaching; they are not portable defaults,
installed-version proof for another system, live acceptance, or certification:

- The built-in datastore-administration role contained broad datastore
  allocation in addition to space, template, and audit privileges.
- A custom human template-builder datastore role was observed with exactly
  `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, and
  `Datastore.Audit`, deliberately excluding `Datastore.Allocate`.
- A built-in VM administration role exposed substantially broader VM,
  configuration, console, snapshot, migration, and guest-agent privileges than
  the repo-derived lifecycle candidate set.
- SDN use plus audit were observed together, while node visibility, global
  next-ID, own-task visibility, guest-agent audit, and minimal cleanup
  requirements still require isolated installed-version tests.

No discovery environment path, role name selected by an operator, resource ID,
account identity, token identity, or other deployment value is copied into this
record.

## Secret, deployment-data, and recovery safeguards

The course teaches a named profile without embedding any value. Existing
profiles and any existing default remain unchanged. Only secret-variable-name
indirection belongs in private configuration; the secret value is captured by
an approved external hidden mechanism and must not enter repository content,
curriculum, configuration values, SQLite, shell history, process arguments,
logs, exceptions, snapshots, screenshots, course answers, or shared evidence.
TLS verification remains enabled.

Deployment values stay in the learner's owner-only private worksheet and
existing private operational state, never in tracked curriculum, progress
answers, this report, or certification data. Live acceptance, if separately
authorized later, must use a newly isolated lifecycle state root that is first
confirmed empty. Before destroy, the operator must make an owner-only backup of
that isolated ownership state. The worksheet and protected backup remain the
recovery authority until cleanup is independently reconciled; filtered or
uncertain state must not trigger a retry or early privilege revocation.

## Scope and certification boundary

The reviewed implementation makes curriculum and narrow documentation/test
changes only. There are no provider/lifecycle/config/schema/certification
changes. The existing admin course remains unchanged. There is no
certification-registry entry for `proxmox/provider-bootstrap`, so digest-bound
maturity remains fail-closed at draft and normal start requires
`--include-drafts`.

Offline evidence cannot prove installed role definitions, privilege semantics,
ACL inheritance, task visibility, token/user intersection, storage/network path
mapping, mutation rights, guest readiness, cleanup, or operator behavior. Manual
confirmations prove only self-attestation. No certification-registry entry may
be added until the entire live protocol below passes for this exact digest.

## Required live protocol — unexecuted

Every item below is **NOT RUN / PENDING**. This report neither requests nor
grants authorization to execute it. A later authorization must identify its
scope privately; resulting shared evidence must remain redacted.

1. **NOT RUN / PENDING:** Record the installed PVE version and final course
   digest without deployment identifiers.
2. **NOT RUN / PENDING:** Inspect installed roles and privileges for every
   candidate endpoint-to-privilege mapping; ambiguity is a blocker.
3. **NOT RUN / PENDING:** Reconcile and summarize the exact effective privilege
   sets for the dedicated user and privilege-separated token independently,
   without paths or identities; extra, missing, or inherited authority blocks
   progression.
4. **NOT RUN / PENDING:** Observe GET-only health success and record its limits;
   do not infer lifecycle, storage, network, guest-agent, or deletion rights.
5. **NOT RUN / PENDING:** Under a separate one-lifecycle authorization and
   isolated empty state, observe successful clone and task waits, start,
   guest-agent/address discovery, stop/delete, and final absence.
6. **NOT RUN / PENDING:** Perform only safe negative tests showing omitted broad
   privileges remain unnecessary, especially broad datastore allocation and
   guest-agent file, filesystem-management, or unrestricted permissions.
7. **NOT RUN / PENDING:** Exercise collision, 403, or equivalent denial handling
   only where it cannot leave uncertain state; filtered inventory or uncertainty
   blocks retry and revocation.
8. **NOT RUN / PENDING:** Positively reconcile resource and storage cleanup,
   completed task state, source preservation, and authorized refreshed absence;
   require confirmation from an independent administrator.
9. **NOT RUN / PENDING:** Record either retained access or completed reverse-order
   rollback, removing only bootstrap-created access after positive cleanup.

Any ambiguous mapping, filtered inventory, unresolved task, uncertain mutation,
or uncertain cleanup is a live blocker. The course remains draft.
