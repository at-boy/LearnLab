# Proxmox Provider Bootstrap Course Design

**Status:** Approved design for later implementation; no curriculum implementation, provider change, permission change, or live acceptance is part of this document.
**Course:** `proxmox/provider-bootstrap`
**Maturity:** `draft`; there is no certification-registry entry or live evidence for this course.
**Starting point:** the current repository state in the implementation worktree; verify the checkout and preserve compatible NixOS-template changes before implementation.

## Purpose and outcome

Add a separate guided course that teaches an authorized learner and their Proxmox administrator to bootstrap the named provider profile LearnLab already expects. The course covers private planning, read-only inventory, the exact current provider API surface, dedicated identity and privilege-separated token setup, custom least-privilege roles and ACLs, secure profile entry, read-only health validation, a separately authorized scratch lifecycle acceptance, positive cleanup reconciliation, and optional access rollback.

The course fills the circular gap between having Proxmox access and having a safe LearnLab runtime token. It does not replace or broaden `proxmox/proxmox-admin`: that existing VM-scoped course keeps its current IDs, environment, lessons, and conceptual token teaching. The new course is optional onboarding for creating an actual profile and proving its runtime authorization.

## Goals

- Teach a reproducible, least-privilege provider bootstrap without storing deployment values or credentials in curriculum or progress.
- Separate permissions used by a human administrator or template builder, a validation-only caller, and the LearnLab runtime token.
- Derive the runtime permission discussion from the current HTTP calls in `src/learnlab/providers/proxmox.py` and their ordering in `src/learnlab/lifecycle.py`.
- Make installed-version inspection and effective user/token permission reconciliation prerequisites to ACL changes and live use.
- Preserve existing profiles and `default_provider` while adding one explicit named profile.
- Establish that GET-only health validation does not prove clone, start, stop, guest-agent, or deletion rights.
- Exercise mutation only under a second, explicit authorization for a named scratch profile and disposable target.
- Fail closed on authorization denial, filtered inventory, resource collision, uncertain mutation, or uncertain cleanup.
- Leave the course draft until a later exact-digest acceptance is authorized, completed, and recorded.

## Non-goals

- Do not change the provider adapter, lifecycle, profile schema, CLI, secret resolver, SSH behavior, state model, or `proxmox/proxmox-admin` behavior.
- Do not add pool placement or pool-aware allocation. The current provider uses the cluster-global next VMID and sends no pool in its clone request.
- Do not automate Proxmox user, token, role, or ACL creation from LearnLab.
- Do not have the course session load settings, resolve secrets, construct a provider, use SSH, or make network requests.
- Do not create, adopt, reconfigure, snapshot, start, stop, or delete infrastructure during ordinary course execution or offline tests.
- Do not prescribe `Administrator`, `PVEAdmin`, an unseparated token, or another broad role as a troubleshooting shortcut.
- Do not prove minimal privileges from a read-only health check, a built-in role name, static documentation, or one development cluster.
- Do not certify the provider-bootstrap course, a profile, a template, or any downstream course as part of implementation.

## Architecture and execution boundary

The new course uses `EnvironmentScope.NONE`. Its lessons contain instructions plus `text-evidence` and `manual-confirmation` verifications only. They may show commands that the learner deliberately runs in a separately identified `Controller` or `Proxmox node` shell, but LearnLab never executes those commands. `remote-command`, `provider-check`, `provider_capability`, and `guest_capabilities` are forbidden in this course.

This is a narrow extension of the current authoring meaning of `scope: none`. The authoring guide currently describes it as suitable for purely conceptual courses. It must also permit learner-operated bootstrap courses when all of the following hold:

1. no LearnLab dependency or verification performs the operation;
2. every operator command names its execution location and is bounded by an explicit checkpoint;
3. mutations have preflight identity checks, expected results, rollback instructions, and fail-closed handling;
4. evidence recorded in LearnLab is non-secret self-attestation or a short conceptual answer, never copied command output or deployment data; and
5. offline completion is not represented as provider or infrastructure validation.

The runtime relationship is therefore:

```text
provider-bootstrap course session
  -> renders generic instructions and records self-attested local progress
  -> makes zero settings, secret, provider, SSH, or network calls

learner-controlled shells, outside the course dependency graph
  -> inspect the installed Proxmox version and current ACL state
  -> perform explicitly confirmed bootstrap changes
  -> enter a secret through an external hidden mechanism
  -> run GET-only LearnLab health validation
  -> only after separate approval, run and clean up one scratch lifecycle
```

No step may ask the learner to paste a profile, endpoint, resource ID, ACL output, username, token identity, secret, task ID, host fingerprint, or inventory listing into a LearnLab answer.

## Current provider contract

The course must explain the provider contract as code-derived behavior, not as a generic Proxmox checklist. Implementation must re-read the provider and lifecycle before authoring, because an endpoint change changes the permission surface.

### GET-only health and validation surface

`learnlab provider test PROFILE` calls `ProxmoxProvider.health_check()`. Provider-aware `learnlab validate COURSE --provider PROFILE` performs offline curriculum validation, resolves only the selected profile and secret, constructs the provider, and calls the same health check before checking declared capability compatibility. The health check currently performs only:

| Request | What LearnLab infers | Important limit |
|---|---|---|
| `GET /version` | API is reachable and returns a version | Does not prove resource visibility or mutation rights. |
| `GET /nodes` | The configured node is visible in the returned list | Permission-filtered output can look like a missing node. |
| `GET /cluster/resources?type=vm` | The configured template ID, name, node, and template flag match | A missing item may be filtered, not absent. |
| `GET /nodes/{node}/qemu/{template_vmid}/config` | The primary boot disk uses the configured storage and `net0` uses the configured bridge | LearnLab does not query storage or network ACL endpoints and cannot prove use rights. |

Health success is necessary but not sufficient. It proves only the observed GET responses for that profile at that time. In particular, it does not prove `GET /cluster/nextid`, clone, task-status, power, guest-agent, or delete authorization. The course must preserve and explain the provider's existing mutation-permission warning.

The provider also exposes four curriculum check names. `api-reachable` repeats `GET /version`; `template-visible` repeats the cluster VM-resource GET; `vm-running` uses that resource GET and verifies the VMID lookup, expected name, and running status but does not compare the returned node with the recorded node; and `guest-agent-ready` uses `POST .../agent/ping`. The first two require no managed environment, while the latter two do. These checks are observations only and do not expand the lifecycle permission set.

### Scratch lifecycle surface

The current lifecycle uses the following provider operations in this order:

1. `GET /cluster/nextid` to allocate a cluster-global VMID.
2. `POST /nodes/{profile_node}/qemu/{template_vmid}/clone` with `newid`, generated name, `full=1`, and configured storage.
3. Repeated `GET /nodes/{node}/tasks/{upid}/status` until the clone task stops successfully.
4. `GET /cluster/resources?type=vm` to locate the new VM and reconcile its generated name.
5. `POST /nodes/{node}/qemu/{vmid}/status/start`, followed by task-status GETs.
6. Repeated `POST /nodes/{node}/qemu/{vmid}/agent/ping`, then `GET /nodes/{node}/qemu/{vmid}/agent/network-get-interfaces` until a usable IPv4 address appears.
7. During cleanup, `GET /cluster/resources?type=vm`, optional `POST .../status/stop` plus task-status GETs, `DELETE /nodes/{node}/qemu/{vmid}` plus task-status GETs, and a final cluster-resource GET proving absence.

The QEMU guest-agent ping uses HTTP POST because that is the Proxmox API shape, but it is semantically read-only: it asks the existing guest agent to respond and must not be described as a guest mutation. HTTP method alone is not the privilege model.

The live protocol must exercise the full sequence, including cleanup and final absence. A passing clone without stop/delete reconciliation is not acceptance.

## Accepted global `/vms` limitation

The current adapter requests a global next VMID and its clone call has no pool parameter. Before the target VM exists, there is no target-specific ACL path to grant. Consequently, the runtime identity needs the installed-version-confirmed allocation and target-lifecycle privileges inherited from a propagated ACL at `/vms`; a non-propagating template-only grant cannot authorize the current design.

This limitation is accepted and must be conspicuous in the course. It gives the runtime identity authority over more VM paths than a pool-scoped design would. Mitigations are a dedicated user and privilege-separated token, narrowly composed custom roles, source-template-specific clone authority, storage/network leaf ACLs, an isolated scratch profile, regular effective-permission review, and optional revocation after positive cleanup. Do not imply that naming conventions constrain Proxmox authorization. Pool support, a VMID reservation service, and a provider redesign are future work, not hidden prerequisites for this course.

## Permission model

All privilege names below are candidates until checked against the learner's installed Proxmox version and proven by dedicated live acceptance. The repository can prove which endpoints it calls; it cannot by itself prove how every supported Proxmox release maps those calls to privileges. Course content must label version-sensitive mappings as `installed-version/live-confirmation-required` and must teach inspection of installed roles, CLI help or API permission metadata before ACL creation.

### Separation of actors

| Actor | Purpose | May receive | Must not receive by default |
|---|---|---|---|
| Authorized bootstrap administrator | Inspect installed privileges; create the dedicated user, custom roles, privilege-separated token, and narrowly scoped ACLs; later perform independent cleanup confirmation and rollback | Only the existing human authority needed for those access-control operations | Runtime credentials, stored token secret, or a recommendation to replace scoped work with `Administrator`/`PVEAdmin` |
| Human template builder | Create or maintain the specifically chosen template and its storage artifacts through the separate template course/operator workflow | Installed-version-confirmed VM/template and storage rights scoped to the template-building task | LearnLab runtime ACLs merely because the same human builds the template |
| Validation-only caller | Run the health GETs and observe only the configured node/template/config | Auditing/read rights for those specific resources | Clone, allocation, power, guest-agent, or delete rights; health success must not be used to infer them |
| LearnLab runtime user plus privilege-separated token | Perform exactly the current disposable lifecycle | The intersection of narrowly scoped user ACLs and token ACLs required by the code-derived matrix | Access-control administration, template conversion, unrelated storage administration, broad datastore allocation, or unrelated VM configuration |

Use a dedicated non-human Proxmox user for LearnLab and a token created with privilege separation enabled. Both the user and token must be granted the intended resource ACLs; effective token authority is their intersection. A user-level grant alone does not prove a separated token has it, and a token ACL cannot exceed its user. The learner must inspect effective permissions for each identity separately after creation and after any change.

### Human bootstrap and template actions

The human side is a different permission surface and must not be folded into the runtime role:

| Human action | Candidate authority | Design requirement |
|---|---|---|
| List installed privileges, roles, users, tokens, and ACLs | Installed audit authority for the access-control objects being inspected | Verify actual command help and whether output is filtered before treating a missing object as absent. |
| Create or modify the dedicated user and privilege-separated token | `User.Modify` candidate at the installed access-control scope | Confirm against the installed version; the secret is captured once into the external hidden mechanism. |
| Create or modify custom roles and resource ACLs | `Permissions.Modify` candidate at the installed access/resource scope | Confirm the role definition and every path/propagation flag after each change. Do not assign this authority to the runtime user/token. |
| Build and convert the selected source template | Action-specific VM/template rights confirmed by the separate template workflow | Do not use broad `PVEVMAdmin` merely because it contains the required subset; keep this human authority out of the runtime role. |
| Allocate template-builder storage at one leaf | A custom datastore role containing only `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, and `Datastore.Audit` where live-confirmed | Exclude `Datastore.Allocate`; inspect the installed role after creation and keep template-building allocation separate from runtime full-clone allocation. |
| Independently reconcile scratch cleanup and revoke access | Read authority sufficient to prove absence, then the previously confirmed access-control modification authority | Cleanup confirmation precedes token/ACL/user/role removal. |

These are candidate privilege names, not a recipe for elevating an unqualified learner. If the person following the course lacks existing authority to perform one of these actions, they stop and hand the worksheet to an authorized administrator. The course never teaches privilege self-escalation.

### Code-derived endpoint-to-privilege matrix

| Provider operation | Resource scope | Candidate installed privilege(s) | Confidence and required proof |
|---|---|---|---|
| `GET /version` | API root | Authenticated API access; no additional candidate asserted | Confirm on installed version. |
| `GET /nodes` | configured node visibility | `Sys.Audit` may be required at the relevant node scope | **Unproven:** PVE 9.2 own visibility and `PVEAuditor` behavior still require isolation testing. Treat filtered output as failure, not absence. |
| `GET /cluster/resources?type=vm` | source template and managed targets | `VM.Audit` | Strong candidate from API semantics; prove source and newly created target visibility with the separated token. |
| `GET .../qemu/{template}/config` | source template | `VM.Audit` | Strong candidate; health must see exact configured template identity. |
| `GET /cluster/nextid` | cluster/global allocation | installed-version-specific audit/allocation authority | **Unproven:** inspect and negative-test PVE 9.2 before naming a minimal privilege. Its global nature does not remove the propagated `/vms` requirement for the later target. |
| `POST .../{template}/clone` | source template | `VM.Clone` and normally `VM.Audit` | Assign at the exact source-template path where supported; prove with a real full clone. |
| same clone request, new target | propagated `/vms` | `VM.Allocate` | Candidate required because the target path does not yet exist. Prove that the custom target role works without unrelated VM configuration privileges. |
| same clone request, target storage | configured storage leaf | `Datastore.AllocateSpace` and `Datastore.Audit` candidates | Prove full-clone allocation. Do not grant `Datastore.Allocate`; add `Datastore.AllocateTemplate` only to the separate human template-builder role when installed behavior requires it. |
| same clone request, configured network | exact installed SDN/bridge path | `SDN.Use`, with `SDN.Audit` if installed visibility requires it | PVE 9.2 discovery found built-in `PVESDNUser` supplies both; prove the exact local ACL path and minimal custom/built-in choice. |
| `GET .../tasks/{upid}/status` | configured node and task | own-task access and possibly node audit authority | **Unproven:** confirm whether the separated token can read all tasks it creates and whether `Sys.Audit` is additionally required. |
| `POST .../status/start` and `.../status/stop` | managed target inherited from `/vms` | `VM.PowerMgmt` | Strong candidate; positive and negative live tests required. |
| `POST .../agent/ping` and `GET .../agent/network-get-interfaces` | running managed target | installed guest-agent audit privilege, likely `VM.GuestAgent.Audit` on PVE 9.2 | **Unproven:** isolate on the installed version. Do not add file read/write, filesystem-management, unrestricted guest-agent, console, or monitor rights without evidence. |
| `DELETE .../qemu/{vmid}` | managed target inherited from `/vms` | `VM.Allocate` candidate, plus any installed storage cleanup requirement | Prove successful removal and task completion with the same token; do not assume clone success proves deletion. |

The recommended role pattern separates source-template clone rights, propagated managed-target lifecycle rights, storage leaf use, network leaf use, and only the node/task audit rights actually shown necessary. A single all-purpose role is easier to mis-scope and makes review harder. Exact role names are learner-selected local values; curriculum may use placeholders but must not ship a real cluster's role, path, user, or token identity.

### PVE 9.2.11 development discovery

The following observations came from one current PVE 9.2.11 development environment. They justify the course's inspection-first design but are not portable defaults or certification evidence:

- `pveum role list` reported built-in `PVEDatastoreAdmin` (`special=1`) with exactly `Datastore.Allocate`, `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, and `Datastore.Audit`. That role is too broad for the template-builder storage leaf because it includes `Datastore.Allocate`.
- A custom non-built-in role (`special=0`) was successfully created with exactly `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, and `Datastore.Audit`. Assigned to the human at one storage leaf, the human's effective `Datastore.*` privileges were exactly those three. A privilege-separated token carrying `PVEAuditor` at that leaf remained limited to `Datastore.Audit`.
- Current-cluster `PVEVMAdmin` effective output included `VM.Allocate`, `VM.Audit`, `VM.Backup`, `VM.Clone`, `VM.Config.CDROM`, `VM.Config.CPU`, `VM.Config.Cloudinit`, `VM.Config.Disk`, `VM.Config.HWType`, `VM.Config.Memory`, `VM.Config.Network`, `VM.Config.Options`, `VM.Console`, `VM.GuestAgent.Audit`, `VM.GuestAgent.FileRead`, `VM.GuestAgent.FileSystemMgmt`, `VM.GuestAgent.FileWrite`, `VM.GuestAgent.Unrestricted`, `VM.Migrate`, `VM.PowerMgmt`, `VM.Replicate`, `VM.Snapshot`, and `VM.Snapshot.Rollback`. This proves the built-in role is broad; it does not prove the minimal LearnLab role.
- The existing SDN-path `PVESDNUser` role yielded `SDN.Audit` plus `SDN.Use`.
- The repo-derived minimal runtime candidates are `VM.Allocate`, `VM.Audit`, `VM.Clone`, and `VM.PowerMgmt`, plus only the installed-version-confirmed guest-agent privilege and the narrowly scoped storage/network/node rights required by the full lifecycle. `VM.GuestAgent.Audit` is likely for PVE 9.2 but has not yet passed isolated negative testing. `/nodes`, global next-ID, and own-task requirements are also not yet proven.

Implementation must not copy any discovery environment's resource paths, role names, IDs, hostnames, users, or token identities into YAML. It must teach the pattern and require local inspection. The datastore pattern deliberately excludes `Datastore.Allocate` and verifies the installed role definition after creation rather than trusting the submitted command.

## Ordered lesson flow

The course has eight ordered lessons. Each lesson begins with prerequisites, a resume/reinspection rule, named execution locations, expected outcomes, stop conditions, and at least one concrete troubleshooting branch.

| Lesson directory / ID | Required outcome |
|---|---|
| `00-safety-and-private-worksheet` | Understand the NONE-scope boundary, identify authorized people and a disposable target, and create an owner-only, non-secret worksheet outside the repository. |
| `01-read-only-inventory` | Inspect installed PVE version, cluster/node/template/storage/network identity, existing users/tokens/roles/ACLs, and collisions without changing them. |
| `02-map-provider-authority` | Map every current provider endpoint to validation-only, source-template, target-VM, storage, network, node/task, and guest-agent authority; acknowledge the propagated `/vms` limitation. |
| `03-create-identity-roles-and-acls` | After explicit checkpoints, create the dedicated user, custom roles, privilege-separated token, and scoped ACLs; inspect effective user and token permissions and retain a precise rollback inventory. |
| `04-add-named-profile` | Add one new secret-safe named profile without replacing an existing profile or `default_provider`; store only the secret variable name. |
| `05-run-get-only-health` | Supply the secret through an external hidden mechanism and run provider/compatibility health checks, while explaining why they do not prove mutation rights. |
| `06-authorize-scratch-lifecycle` | Obtain separate authorization, run exactly one disposable clone/start/agent/address/stop/delete lifecycle, test intended denial boundaries where safe, and preserve state on any uncertainty. |
| `07-reconcile-and-rollback` | Positively reconcile resource absence, obtain independent administrator cleanup confirmation, then retain the profile or optionally revoke only the access proven safe to remove; distinguish progress from certification. |

Keep lesson, step, and verification IDs stable once shipped. Separate conceptual answers from action attestations so a manual confirmation does not duplicate an objective check. Course prompts record only short non-secret concepts such as `intersection`, `read-only`, `propagated`, or `self-attested`.

## Lesson requirements

### Safety, worksheet, and inventory

The first lesson must explain that LearnLab is only displaying instructions. The learner is responsible for every command run outside the session. Identify three different boundaries before continuing: the existing human administrator authority, the dedicated runtime identity to be created, and one scratch lifecycle authorized for destruction. Production resources and existing LearnLab-managed environments are out of scope.

The private worksheet is owner-only and external to the repository. It may contain non-secret local identifiers needed for reconciliation: installed PVE version, intended node/template/storage/network, chosen placeholder-to-local role mapping, intended user/token identity, ACL paths and propagation flags, scratch ownership observations, and rollback items. It must not contain the token secret, passwords, private keys, copied authorization headers, or raw secret-manager output. No worksheet value is pasted into LearnLab.

Inventory is read-only. The learner verifies installed command help and privilege names before using examples, lists current roles and ACLs, checks that proposed names are unused, and confirms the exact source template by more than VMID. A failed query, 403, incomplete/filtered list, duplicate identity, or unexpected existing object stops the course. It is never permission to create over or delete the conflicting object.

### Role, identity, token, and ACL creation

The mutation lesson must be deliberately granular:

1. review the pre-change inventory and rollback list;
2. independently confirm authority to create the dedicated identity and access objects;
3. inspect installed command help immediately before each command family;
4. create or verify each custom role and then re-list its effective privilege definition;
5. create the dedicated user without borrowing a human administrator identity;
6. create exactly one token with privilege separation enabled and capture its one-time secret only into an approved hidden secret mechanism;
7. add user ACLs and token ACLs one resource scope at a time, with the intended propagation flag explicit;
8. query effective permissions for the user and token separately and compare them to the worksheet matrix; and
9. stop before profile entry if there is any extra authority, missing authority, ambiguous path, or unexpected inheritance.

The curriculum must not embed a finished cluster-specific `pveum` command. It should show parameterized command shapes only after requiring installed-version help inspection, and implementation/live review must replace any stale syntax. Expected output descriptions focus on selected role definitions, `privsep=1`, exact path and propagation, and the user/token intersection. They must never invite copying the secret or full ACL listing into progress.

If a partially completed mutation fails, do not restart the whole sequence blindly. Re-inventory the exact object, distinguish absent from filtered/denied, and either continue from confirmed state or invoke the rollback protocol. Never add `Administrator`, `PVEAdmin`, or broad built-ins to diagnose a 403.

### Named profile and secret handling

The profile lesson uses the current `ProxmoxProfile` schema: `type`, `api_url`, `token_id`, `token_secret_env`, `template_vmid`, `template_name`, `node`, `storage`, `network`, `ssh_user`, `ssh_identity_file`, `tls_verify`, and optional `template_capabilities`. It explains each field without supplying a real value.

The learner opens their XDG config in a local editor, takes an owner-only backup, chooses an unused provider table name, and preserves every existing provider. An existing `default_provider` is never replaced. Only a genuinely new configuration with no default may receive one, and subsequent commands still select the new profile explicitly. A duplicate table or conflicting name is a stop condition.

`token_secret_env` stores only a unique environment-variable name. The secret value is captured externally when the token is created, then an external hidden shell read or secret manager populates that named environment variable before LearnLab starts. LearnLab itself resolves only the environment variable; it has no token-secret stdin or interactive-prompt interface. The secret never appears in the repository, curriculum YAML, TOML, SQLite, shell history, process arguments, command output, logs, exceptions, test fixtures, approval transcripts, screenshots, or snapshots. Shell tracing must be off, and the value is removed from the process environment after use. TLS verification stays enabled; certificate, hostname, CA, and clock problems are repaired rather than bypassed.

### GET-only health, then separate live acceptance

The learner first runs the selected profile's `learnlab provider test` and relevant provider-aware validation commands. The course names the exact four GET requests those checks currently make and requires the learner to explain that storage/network matching is inferred from template configuration, not direct authorization testing. A PASS is not permission to mutate.

Only after GET-only results are understood may the learner request a separate live authorization. That authorization names the scratch profile, source template, intended target storage/network, time window, one disposable lifecycle, cleanup obligation, and people responsible for independent reconciliation. It is not implied by starting or completing the NONE-scope bootstrap course.

The learner-facing live acceptance uses the existing `proxmox/proxmox-admin` start/destroy path with the scratch profile and a newly created, isolated XDG state root. Isolating state ensures that the destroy command sees exactly the one acceptance environment rather than unrelated LearnLab environments. The learner first confirms that the isolated state is empty, then from a separate controller shell explicitly runs the equivalent of `learnlab start proxmox/proxmox-admin --provider "$PROFILE" --include-drafts`, permits creation of exactly one managed environment, completes enough of its ordinary first lesson to prove the runtime environment and guest path, and exits cleanly. Before invoking destroy, the learner makes an owner-only backup of the isolated lifecycle ownership state and preserves the private worksheet. The normal destroy flow then runs with an explicit preserve-progress or erase-progress choice. The implementation must provide exact state-isolation and backup commands, expected output, checks that the normal config/profile remains selected, and cleanup of the scratch state only after independent reconciliation is complete. The provider-bootstrap course does not invoke these commands, and the live authorization is not implied by reaching the lesson. The repository's opt-in lifecycle test may be an additional reviewer diagnostic, but it does not replace the learner-facing start/destroy acceptance or certify either course. Live review records generic pass/fail observations, installed PVE version, LearnLab revision, and the provider-bootstrap course digest only; it excludes deployment identifiers and secrets.

Authorization failures are evidence, not invitations to broaden roles. A 403 returns to effective user/token/path inspection. A clone collision returns to inventory and ownership reconciliation. Filtered inventory, timeout, malformed response, transport loss, uncertain clone outcome, or uncertain delete outcome blocks retry and ACL revocation until independently reconciled. The current adapter does not guarantee preservation of its environment record when an ACL-filtered resource list omits a VM or when the final post-delete lookup reports no row. The operator therefore preserves the private worksheet and protected pre-destroy state backup as the authoritative recovery evidence until an administrator completes reconciliation.

## Safety and rollback protocols

### Fail-closed rules

- Never infer absence from one failed lookup. Require a successfully refreshed authorized inventory and corroborating task/storage state.
- Never delete or overwrite a resource based only on VMID, name, or the result of `GET /cluster/nextid`.
- Never retry clone or delete after an uncertain outcome until the intended resource is reconciled by full identity and ownership.
- Never solve 403 by adding `Administrator`, `PVEAdmin`, unscoped `PVEVMAdmin`, unseparated token authority, or `Datastore.Allocate`.
- Never continue after unexpected privilege inheritance, ACL propagation, extra role membership, or a user/token effective-permission mismatch.
- Never revoke cleanup authority while a LearnLab-managed or scratch resource remains, might remain, or has uncertain task state.
- Never treat course progress, provider health, compatibility declarations, or historical PVE 9.2 observations as live acceptance.

### Positive cleanup reconciliation

After the scratch lifecycle, reconcile the generated name and VMID against the protected pre-destroy ownership record, private worksheet, task history, node, template ancestry, storage artifacts, and authorized cluster inventory. Successful deletion requires a completed delete task, no active or unresolved task for the scratch resource, an authorized refreshed inventory where the exact managed identity is absent, expected attached scratch storage no longer present, and the source template still present. A 404 or missing row without proven inventory visibility is insufficient. Completed task history is retained as audit evidence rather than treated as a residual resource.

An administrator other than the runtime token independently confirms that no managed scratch VM, active or unresolved task, or residual scratch storage remains. Until that confirmation is recorded privately as pass/fail, the learner retains the worksheet, protected state backup, and runtime permissions for recovery.

### Optional rollback or retention

After positive cleanup, the learner chooses one of two explicit outcomes:

- **Retain:** keep the named profile, dedicated user/token, roles, and ACLs for future LearnLab use; review them periodically and preserve the secret only in the approved external mechanism.
- **Revoke:** disable or delete the token first, remove only ACL entries created by this bootstrap, remove the dedicated user only if it has no remaining ownership or use, and remove custom roles only after proving no ACL or user references them. Re-inventory after each change.

Rollback is reverse-order and itemized from the pre-change worksheet. Shared roles, users, ACLs, templates, storage, networks, or unrelated VMs are never removed. Any unexpected reference or denied/filtered query stops rollback for administrator review.

## Files and integration impact

Implementation is expected to change only the following areas:

- `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml` and eight `lessons/*/lesson.yaml` files: the new packaged NONE-scope course.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`: replace the current generic account-setup handoff with a cross-link to `proxmox/provider-bootstrap`, while keeping direct advanced setup as an option and preserving the NixOS course's no-provider execution boundary.
- `docs/LearnLab-Course-Authoring-Guide.md`: add only the narrow `EnvironmentScope.NONE` learner-operated bootstrap exception defined above; retain the prohibition on remote/provider checks and automatic side effects.
- `README.md`: list the optional provider-bootstrap path and distinguish it from `proxmox/proxmox-admin` and template-bootstrap courses.
- `tests/test_provider_bootstrap_course.py`: course order/content/security/permission-matrix tests.
- `tests/test_nixos_template_course.py`: assert the configure-provider lesson points learners to the new optional bootstrap course without making it a prerequisite or provider call.
- `tests/test_cli.py`: actual start/save/resume coverage with settings, secret, provider, SSH, and network dependency tripwires.
- `tests/test_packaging.py`: extend the existing single-build wheel test to discover and load the new course without adding a second wheel build.
- `docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md`: offline review plus a clearly separate, unexecuted live protocol.

No collection manifest edit is needed because course discovery is directory-based. Do not edit `src/learnlab/collections/certifications.yaml`; absence of a matching record is required. Do not change `src/learnlab/providers/proxmox.py`, `src/learnlab/lifecycle.py`, config parsing, or the live test merely to make the authored permission claims pass.

## Validation and testing requirements

### Offline tests

- Load `proxmox/provider-bootstrap` through the real catalog and assert the exact eight-lesson order.
- Assert every effective environment is `none`, with no provider or guest capability and no `remote-command` or `provider-check` verification.
- Start the real draft course with `--include-drafts`, save/exit, and resume existing progress while tripwires make `load_settings`, requested-profile loading, token resolution, provider construction, provider requests, SSH construction/execution, and network clients fail if called.
- Exercise positive and negative `text-evidence` answers and confirm manual actions remain labeled self-attested.
- Assert the content distinguishes GET-only health from the full lifecycle, names the semantically read-only POST agent ping, and covers every current provider endpoint.
- Assert the matrix includes the propagated `/vms` limitation, no pool support, separate source/target/storage/network/node/agent scopes, privilege separation, and installed-version/live-confirmation labels.
- Assert content prohibits `Administrator`/`PVEAdmin` fallback, `Datastore.Allocate`, mutation on collision/403/filtered inventory, revocation before positive cleanup, and secrets in evidence.
- Assert the profile instructions preserve existing providers/defaults and store only the secret environment-variable name.
- Scan new course content and documentation for placeholder mistakes and accidental example infrastructure identities. Generic metavariables are allowed; realistic endpoints, hostnames, VMIDs, token identities, or secrets are not.
- Assert the NixOS cross-link and authoring-guide exception are present and narrowly worded.
- Extend the existing single-build wheel test so it builds/installs once and loads the new course from installed package resources.
- Assert the certification registry has no `proxmox/provider-bootstrap` entry and the effective maturity is `draft`.

Normal tests and `learnlab validate` are offline. They must not execute displayed `pveum`, LearnLab provider, lifecycle, shell, or network commands. Run focused course/CLI/packaging tests, the complete non-live suite, `git diff --check`, and the repository's normal formatting/type gates. Existing `proxmox/proxmox-admin` validation findings must remain unchanged rather than being hidden by unrelated edits.

### Live evidence

Live work is outside normal implementation and requires a new explicit authorization. The protocol must record, without personal identifiers:

1. the installed PVE version and final course digest;
2. installed role/privilege inspection results for every candidate mapping;
3. exact effective privilege sets for the dedicated user and privilege-separated token, summarized without paths or identities;
4. GET-only health success and its limitations;
5. one full scratch lifecycle with successful task waits, guest-agent/address discovery, stop/delete, and final absence;
6. safe negative tests showing omitted broad privileges remain unnecessary, especially datastore allocation and guest-agent file/unrestricted permissions;
7. collision/403 or equivalent denial handling where it can be tested without leaving uncertain state;
8. positive resource cleanup plus independent administrator confirmation; and
9. retained-access or completed-rollback status.

If any endpoint-to-privilege mapping remains ambiguous, any inventory appears filtered, or cleanup is uncertain, the result is a live blocker. Keep the course draft and do not create a certification record.

## Offline/live evidence boundary

Repository inspection proves the current HTTP methods, paths, parameters, call order, secret-redaction intent, NONE-scope dependency bypass, and digest-bound maturity behavior. Offline curriculum tests can prove that the instructions accurately reflect those interfaces and contain the required safety language.

Offline work cannot prove Proxmox privilege semantics, installed role definitions, ACL inheritance, task visibility, token/user intersection on a particular release, network/storage path mapping, mutation rights, guest readiness, cleanup, or operator behavior. The PVE 9.2.11 observations are development discovery only. Only the separately authorized protocol against the final digest can provide current live evidence.

Manual confirmations prove only that a learner attested to an action. They do not transform operator-run commands into objective checks and do not certify the course.

## Compatibility and migration

- The change is additive: existing profile names, config files, state, CLI commands, provider fingerprints, and VM ownership records remain valid.
- `proxmox/proxmox-admin` keeps its VM-scoped environment and two existing lessons without content or digest changes.
- Existing learners may continue creating profiles directly. The new course is guidance, not a mandatory gate enforced by config loading or `learnlab start`.
- The NixOS template course gains an optional cross-link. Because editing that lesson changes its course digest, its maturity must continue to fail closed unless a new matching record exists; do not reuse historical acceptance.
- Course discovery should find the new directory without a hard-coded collection course list.
- The authoring-guide exception does not authorize ordinary NONE-scope courses to perform side effects, nor does it permit provider/remote verification types.
- Supporting additional Proxmox releases means rechecking installed privileges and live behavior; curriculum must not branch on one cluster's names or PVE 9.2 paths.
- Pool-aware restriction would require a separate provider/interface design and migration. It is not implemented or implied here.

## Acceptance criteria

The design is implemented when all of the following are true:

1. `learnlab start proxmox/provider-bootstrap --include-drafts` runs the packaged course without a profile and makes zero settings, secret, provider, SSH, or network calls.
2. The eight lessons guide an authorized learner from private read-only inventory through scoped setup, named profile entry, GET-only validation, separately authorized lifecycle acceptance, and cleanup/optional rollback.
3. The course's API matrix exactly matches the current provider and lifecycle, including global next-ID, no pool clone parameter, task polling, semantically read-only POST agent ping, interface discovery, stop, delete, and final locate.
4. Human bootstrap/template, validation-only, and runtime-token permissions are clearly separated; all unproven PVE mappings are labeled installed-version/live-confirmation-required.
5. The PVE 9.2.11 evidence is documented only as development discovery, including the custom datastore role pattern that excludes `Datastore.Allocate` and the broad built-in-role findings.
6. The course explicitly accepts propagated `/vms` runtime authority as a current limitation and does not add pool support.
7. Dedicated user, privilege-separated token, custom role verification, per-scope ACLs, effective user/token reconciliation, and reverse-order rollback are explicit checkpoints.
8. Collisions, 403s, filtered inventory, permission ambiguity, mutation uncertainty, and cleanup uncertainty fail closed without broad-role fallback.
9. No access is revoked while managed resources remain or might remain, and an administrator independently confirms positive cleanup first.
10. Secrets never enter tracked content, TOML values, SQLite, logs, exceptions, test snapshots, course answers, or shared evidence; only the environment-variable name and an external hidden mechanism that populates it are taught. Deployment identifiers never enter tracked curriculum, course answers, or shared evidence, while the existing private profile and isolated lifecycle ownership state may store the non-secret identifiers required for operation and cleanup.
11. The NixOS configure-provider lesson links to the new optional course, the authoring guide contains the narrow NONE-scope exception, and existing `proxmox/proxmox-admin` behavior is unchanged.
12. Focused tests, complete offline tests, packaging verification, validation, formatting/type gates, and `git diff --check` pass without live/provider/network activity.
13. `src/learnlab/collections/certifications.yaml` contains no entry for the course, so it remains draft and requires `--include-drafts`.

## Spec self-review

- **Placeholders:** curriculum may use visibly generic metavariables, but shipped text must not contain unfinished markers, example secrets, or realistic deployment values.
- **Consistency:** NONE scope governs the course session; separately authorized learner-run commands are outside the dependency graph and do not weaken that guarantee.
- **Scope:** this design adds curriculum and narrow documentation/tests only; provider permission automation, pool support, provider refactoring, and live execution remain separate work.
- **Ambiguity resolved:** health is GET-only; guest-agent ping is semantically read-only despite POST; runtime permissions are candidates until installed/live proof; global `/vms` propagation is accepted rather than disguised; cleanup proof precedes any revocation; draft status persists without an exact matching registry record.
