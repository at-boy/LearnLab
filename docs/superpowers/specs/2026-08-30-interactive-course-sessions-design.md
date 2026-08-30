# Interactive Course Sessions Design

## Purpose

Turn `learnlab start` from a silent environment-provisioning command that prints one lesson and exits into a responsive, resumable, terminal-first course session.

The change addresses three observed problems:

1. environment creation can take long enough to look hung because no lifecycle feedback is displayed;
2. the CLI returns to the shell immediately after printing lesson content instead of guiding the learner through verified steps; and
3. the course-level active-environment guard prevents starting the next lesson even though the environment may be intended for reuse.

The curriculum designer, not the CLI, decides whether lessons need no environment, a fresh environment, or a shared course environment.

## Scope

This increment includes:

- explicit curriculum environment scopes;
- structured provisioning progress events and terminal activity feedback;
- an interactive, resumable course session;
- persisted step and verification progress;
- multiple ordered verifications per step;
- remote-command, text-evidence, manual-confirmation, and provider-check validators;
- safe course-environment reuse and confirmed lesson-environment replacement;
- migration of existing local state; and
- updated Proxmox curriculum demonstrating the new schema.

This increment does not include a web interface, remote progress synchronization, arbitrary Boolean validator expressions, multi-VM lessons, concurrent course sessions in one terminal, automatic AI grading, or untrusted course packages from third parties.

## Curriculum Environment Policy

Every course declares an environment scope:

```yaml
environment:
  scope: course
  provider_capability: proxmox.vm
```

Supported scopes are:

- `course`: one environment is created and reused for all lessons in the course;
- `lesson`: each lesson receives its own environment; advancing to another lesson replaces the previous lesson environment after confirmation; and
- `none`: the course or lesson does not require a disposable VM.

A lesson may override the course scope:

```yaml
environment:
  scope: none
```

The effective scope is the lesson override when present, otherwise the course scope.

`provider_capability` is an abstract capability such as `proxmox.vm`. It does not name a user's provider profile or infrastructure. It is required for `course` and `lesson` scopes and forbidden for `none`.

For `course` scope, an existing environment is reused only when all recorded ownership checks pass: provider profile, provider fingerprint, endpoint, VMID, and expected VM name. A mismatch fails closed and directs the user to the safe destroy/recovery flow.

For `lesson` scope, an environment belongs to one lesson. Moving to another lesson displays the exact existing VM and requires confirmation before stopping and deleting it. Cancellation preserves the environment and progress. A replacement is created only after confirmed deletion.

For `none`, provider configuration and secret resolution are skipped entirely.

## Step and Verification Schema

Each lesson contains ordered steps. Each step contains an ordered, nonempty `verifications` list. A validator type may appear any number of times in one step as long as every verification has a unique ID.

```yaml
steps:
  - id: inspect-system
    title: Inspect the system
    instructions: Confirm the operating system and active services.
    verifications:
      - id: nixos-release
        type: remote-command
        command: grep -q '^ID=nixos' /etc/os-release

      - id: ssh-active
        type: remote-command
        command: systemctl is-active --quiet sshd

      - id: explain-result
        type: text-evidence
        prompt: What does the ID field identify?
        matches: '(?i)nixos'

      - id: provider-visible
        type: provider-check
        check: guest-agent-ready

      - id: reviewed-output
        type: manual-confirmation
        prompt: Confirm that you reviewed the complete output.
```

All verifications are required. They run in their declared order. The step completes only when every verification passes. The lesson completes only when every step completes.

Nested `all`, `any`, and threshold logic are deliberately excluded. A future schema version can add logical groups without changing the meaning of this version's flat all-required list.

### Common verification fields

Every verification has:

- `id`: stable identifier unique within the step;
- `type`: one of the four supported validator types; and
- optional `failure_message`: safe learner-facing guidance displayed after failure.

Unknown fields are rejected. Verification IDs use the same safe identifier grammar as collection, course, lesson, and step IDs.

### `remote-command`

```yaml
- id: nixos-release
  type: remote-command
  command: grep -q '^ID=nixos' /etc/os-release
  timeout_seconds: 15
```

LearnLab executes the curriculum-authored command non-interactively over SSH in the recorded lesson VM. Exit status zero passes; nonzero fails. The command is passed as one remote command argument rather than interpolated into a local shell command.

`remote-command` requires an active environment and is rejected during curriculum validation when its effective scope is `none`. `timeout_seconds` is optional, bounded from 1 through 300, and defaults to 30.

Captured stdout and stderr are bounded and redacted before display or persistence. The validator does not run learner-supplied text as a command.

### `text-evidence`

```yaml
- id: explain-result
  type: text-evidence
  prompt: What does the ID field identify?
  matches: '(?i)nixos'
```

LearnLab prompts for bounded learner text. The verification declares exactly one of:

- `equals`: exact comparison after trimming surrounding whitespace; or
- `matches`: a regular expression searched against the bounded response.

Regular expressions are compiled when curriculum loads. Invalid expressions reject the curriculum before a session starts. Evidence is limited to 8 KiB before validation and storage.

### `manual-confirmation`

```yaml
- id: reviewed-output
  type: manual-confirmation
  prompt: Confirm that you reviewed the complete output.
```

LearnLab displays the prompt and asks for an explicit yes/no response. A yes passes and is stored as self-attested. A no leaves the verification incomplete.

The UI always labels this result `self-attested`; it never presents manual confirmation as objective verification.

### `provider-check`

```yaml
- id: provider-visible
  type: provider-check
  check: guest-agent-ready
```

Provider checks are named, read-only checks registered by the provider adapter. The initial Proxmox checks are:

- `api-reachable`;
- `template-visible`;
- `vm-running`; and
- `guest-agent-ready`.

Checks that target an environment require an active environment. Provider checks never create, start, stop, reconfigure, or delete infrastructure.

## Interactive Course Session

The main entry point remains:

```text
learnlab start <collection>/<course> [--provider <profile>]
```

`start` now means start or resume:

1. load and validate the course;
2. load local lesson, step, verification, and environment state;
3. offer the first incomplete lesson by default;
4. select the effective environment scope;
5. reuse, replace, create, or skip an environment according to that scope;
6. enter the interactive lesson loop at the first incomplete verification; and
7. remain open until the lesson completes or the learner chooses save-and-exit.

An explicit alias is also available:

```text
learnlab resume <collection>/<course> [--provider <profile>]
```

`resume` requires existing course progress or environment state and otherwise explains that `learnlab start` should be used. Both commands use the same session implementation.

### Session presentation

The CLI presents one step at a time:

```text
Lesson: First Contact
Step 1 of 3: Identify the operating system

Connect to the machine and inspect /etc/os-release.

Verification 1 of 2: NixOS release
Press Enter when you are ready for LearnLab to check it, or type q to save and exit.
```

After a failed verification, LearnLab displays the declared failure guidance or a safe default, retains the environment, and offers retry or save-and-exit. Passing a verification immediately persists the result before the next verification is shown.

After all steps pass, LearnLab marks the lesson complete and offers:

- continue to the next lesson;
- review another lesson; or
- save and exit.

If the next lesson uses the same course-scoped environment, it is reused. If it requires replacement, the destructive confirmation happens before teardown. If it requires no environment, the session continues without provider access; an existing course-scoped environment remains recorded for later course lessons rather than being destroyed implicitly.

## Provisioning Progress

Lifecycle operations emit structured progress events instead of writing terminal output directly:

```text
environment-requested
allocating-vmid
clone-requested
clone-waiting
clone-complete
start-requested
start-waiting
guest-agent-waiting
address-discovery
environment-ready
```

Each event contains:

- event kind;
- safe human-readable message;
- elapsed monotonic time;
- optional VMID after allocation; and
- optional attempt count for polling events.

No event contains credentials, authorization headers, raw provider responses, or unredacted exceptions.

The lifecycle service accepts a progress observer. The CLI observer renders one active line with an animated spinner and elapsed time, updating the message as stages change. When output is not an interactive terminal, animation is disabled and stage messages are printed as newline-delimited text. This makes logs and tests deterministic.

The first message is emitted before any provider request, so a learner receives immediate confirmation that environment creation has started. Polling emits periodic heartbeat events even when the provider state has not changed.

Progress rendering stops cleanly on success, failure, keyboard interruption, or save-and-exit. Provider and lifecycle behavior remain independent of the terminal UI.

## Validation Architecture

Validators implement a common protocol:

```text
validate(context, verification) -> VerificationResult
```

`ValidationContext` supplies only the dependencies permitted for that validator: state store, current environment, SSH executor, provider, and safe prompt interface. Validators cannot obtain a token secret unless their provider dependency already encapsulates it.

`VerificationResult` contains:

- `passed`;
- safe summary;
- validator type;
- self-attested flag;
- bounded evidence suitable for persistence; and
- completion timestamp.

A registry maps validator type to implementation. Curriculum loading proves that the type exists; session execution dispatches through the registry.

The SSH executor is a focused component separate from SSH command rendering. It uses:

- the configured SSH user and identity file;
- the environment's isolated `known_hosts` file;
- batch/non-interactive mode;
- connection and command timeouts; and
- captured bounded output.

It never disables host-key checking and never writes to the user's normal SSH host-key database.

## State Model and Migration

Existing databases are migrated in place after the existing legacy-filename migration resolves the authoritative database.

New state includes:

- effective environment scope on attempts/environments;
- current lesson and step for a course session;
- step status (`not_started`, `in_progress`, `completed`);
- verification status (`not_started`, `passed`, `failed`);
- verification attempt count;
- validator type;
- bounded evidence;
- self-attested flag; and
- created, attempted, and completed timestamps.

Verification state is keyed by collection, course, lesson, step, and verification IDs. Curriculum updates that remove an ID do not silently reassign prior progress to another item.

The migration is transactional and additive. Existing lesson completion remains authoritative. For an already completed lesson, its steps and verifications are treated as completed legacy progress without inventing evidence. The UI labels this `completed before step verification tracking` when reviewed.

Existing environments created before scope tracking retain safe ownership metadata from the current version. Their scope is derived from the course when first resumed. If the current curriculum cannot resolve the course or conflicts with the recorded environment, reuse fails closed.

Text evidence and command output are bounded before persistence. Token secrets, provider authorization, private keys, and complete raw HTTP responses are never stored.

## Interruption and Recovery

`Ctrl-C` during provisioning preserves the existing partial-environment semantics and prints the safe recovery command.

`Ctrl-C` or save-and-exit during a lesson persists all verification results completed before interruption. The current incomplete verification remains resumable.

A failed verification never:

- completes the step or lesson;
- destroys an environment;
- clears earlier successful verifications; or
- changes provider configuration.

An environment that disappears outside LearnLab fails ownership/existence checks on resume. LearnLab reports the missing environment and offers a safe new-environment path according to curriculum scope; it does not silently reuse a different VM with the same VMID.

## CLI Compatibility

`learnlab progress complete <collection>/<course>/<lesson>` remains available as an explicit administrative override. It requires confirmation and records that completion was manually overridden rather than validator-derived. The command explains that normal learners should complete lessons through `start` or `resume`.

The existing `destroy` and `reset` safety rules remain unchanged. Reset additionally clears step and verification progress within its selected scope. Destroy's preserve-progress mode preserves completed lesson, step, and verification results while clearing attempts and transient session/environment state.

## Error Handling

The CLI distinguishes:

- curriculum schema errors;
- incompatible environment scope;
- provider/profile failures;
- environment ownership mismatch;
- SSH connection timeout;
- remote verification command timeout;
- failed remote verification;
- invalid or oversized text evidence;
- failed provider check; and
- state migration or persistence failure.

All errors identify the current course, lesson, step, and verification where applicable. Secret values and private infrastructure response bodies remain redacted and bounded.

## Testing Strategy

All semantic behavior is developed test-first with observed failure before implementation.

Test layers include:

- curriculum tests for all three scopes, lesson overrides, missing/forbidden capability fields, duplicate verification IDs, repeated validator types, type-specific required/forbidden keys, invalid regex, and all-required ordering;
- state tests for additive migration, legacy completed lessons, step and verification persistence, retry counts, override provenance, reset scope, and preserve-progress behavior;
- lifecycle tests for structured event order, immediate first event, polling heartbeats, safe payloads, observer failure isolation, and course/lesson/none scope behavior;
- validator unit tests for remote exit status, timeout, bounded/redacted output, regex/equality evidence, multiple confirmations, and read-only provider checks;
- session tests for first-incomplete resume, retry, save-and-exit, next-lesson continuation, course reuse, lesson replacement confirmation, none-scope provider avoidance, and external VM disappearance;
- CLI tests for spinner behavior on TTY, deterministic newline output off-TTY, immediate life-sign output, `start`/`resume`, and manual completion confirmation; and
- packaging tests proving the installed curriculum contains the new schema.

Normal tests remain offline. Provider and SSH behavior use behavioral fakes or loopback servers. Live Proxmox testing stays explicitly opt-in.

## Success Criteria

The increment is complete when a learner can:

1. run `learnlab start proxmox/proxmox-admin` and immediately see provisioning activity;
2. observe safe stage/heartbeat output until the environment is ready;
3. complete multiple ordered verifications of repeated validator types in one step;
4. receive specific feedback and retry a failed verification without losing the VM or earlier progress;
5. exit and resume at the first incomplete verification;
6. advance to the next lesson using a shared course environment when curriculum declares `course` scope;
7. replace a lesson-scoped environment only after explicit confirmation;
8. complete no-environment lessons without provider configuration; and
9. retain the current destroy/reset security, ownership, and progress-preservation guarantees.
