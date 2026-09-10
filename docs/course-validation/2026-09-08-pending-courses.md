# Pending courses: offline review and live blockers

Offline review date: **2026-09-10**. The filename identifies the original workstream.
All six courses remain **draft**. No live acceptance, provider-aware validation,
SSH operation, or certification occurred. `certifications.yaml` remains empty.
Offline tests establish structural and regression contracts, not guest compatibility.

## Corrections and outstanding live evidence

- **nginx (Debian 13 and NixOS):** NixOS locations now belong to named virtual
  hosts; runtime listener/response, fresh proxy token/header, and fresh log-offset
  probes replace weak evidence. Debian nginx uses its privileged executable path.
  Isolated invalid configuration replaces relative generation rollback. Live
  blockers: fresh-image packages/tool paths, evaluated NixOS modules, active
  listeners and proxy headers, log rotation/retry, cumulative endpoints,
  failure remediation, resume, and cleanup have not been exercised. Timed-out
  package/rebuild state must be inspected before retry.
- **nftables (Debian 13 and NixOS):** NAT is excluded from course ordering and
  retained as explicitly blocked draft content requiring multi-machine ingress.
  Logging uses a non-loopback namespace/veth probe with fresh journal evidence,
  route-overlap rejection and owned-resource cleanup. Snapshot/revert timers
  protect activation; NixOS builds precede timer arming. Live blockers: namespace
  privileges, actual packet traversal, kernel logging/journal timing, tools,
  console-backed snapshot recovery, new SSH connection preservation, and NixOS
  activation remain untested. Static IPv4 is required; IPv6/DHCP are outside
  scope. SIGKILL may leave probe resources requiring ownership inspection and
  scoped cleanup. An activation timeout never proves rollback succeeded.
- **systemd (Debian 13 and NixOS):** Fresh invocation/output probes cover restart,
  dependencies, environment, PrivateTmp, timers and missing-input capstone
  recovery. Account creation is bounded/retry-safe; generated-unit inspection,
  escaping and NixOS activation wording are corrected. Live blockers: fresh
  template compatibility, Nix expression evaluation, effective sandbox behavior,
  journal availability, timer scheduling, generated units, cumulative state,
  failed-check remediation, resume and teardown remain untested. Failed probes
  may leave partly changed units/files; inspect before scoped retry.

## Operator gate

No scratch profile has been selected and no explicit destructive-test approval
has been given. Before any live operation the operator must select scratch
profiles and approve each exact course, compatible fresh template capability set,
and cleanup behavior. Provider-aware validation is pending too. Run courses
serially on disposable infrastructure. Destroy through LearnLab, then verify
absence. Failed or uncertain cleanup blocks certification until reconciled;
never delete by VMID alone. Do not record personal infrastructure identifiers
or secrets in this report or the registry.

The following are canonical course digests calculated with `course_digest` from
final course content; they are not live certificates. Recalculate after edits.
Declared capabilities below are requirements, not verified template properties.

## `nginx/nginx-basics`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/nginx/courses/nginx-basics/`.

`course_digest`: `69bb8d33b123916521b67904be8a2976e464f639df14e718cb4ac9a3d5c0d7aa`

Declared capabilities: `os.debian.13`, `tool.curl`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.

## `nginx-nixos/nginx-basics`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/nginx-nixos/courses/nginx-basics/`.

`course_digest`: `bc735b5d3c29f132ea9d42e60b1fe37baec5c07044f3336aab1cbc96a01b779b`

Declared capabilities: `os.nixos`, `tool.curl`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.

## `nftables-debian13/nftables-basics`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/nftables-debian13/courses/nftables-basics/`.

`course_digest`: `5e2715d8e0ec9efecbd095e61a516346587db1bda652e6c43af768e2aada0c11`

Declared capabilities: `os.debian.13`, `tool.nft`, `tool.ip`, `tool.curl`, `tool.python3`, `tool.systemctl`, `tool.systemd-run`, `tool.journalctl`, `tool.timeout`, `tool.sudo`, `tool.apt`, `tool.dpkg`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.

## `nftables-nixos/nftables-basics`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/nftables-nixos/courses/nftables-basics/`.

`course_digest`: `6d0c76398fcda67a98ff98e4145d91ec8070179c54bcf17a6b8219d83c205e50`

Declared capabilities: `os.nixos`, `tool.nft`, `tool.ip`, `tool.curl`, `tool.python3`, `tool.systemctl`, `tool.systemd-run`, `tool.journalctl`, `tool.timeout`, `tool.sudo`, `tool.nixos-rebuild`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.

## `systemd-debian/service-authoring`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/systemd-debian/courses/service-authoring/`.

`course_digest`: `0a3ded762ae6e7abc4549c0793412698b2549edeed264ec0d48540e6b09ddd5d`

Declared capabilities: `os.debian.13`, `tool.systemd`, `tool.coreutils`, `tool.sudo`, `tool.useradd`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.

## `systemd-nixos/service-authoring`

Maturity: **draft**.

Canonical course directory: `src/learnlab/collections/systemd-nixos/courses/service-authoring/`.

`course_digest`: `84c1ed08fdc8fb551aa43ece7e1ca585f0bec8ad05daf43f42ce696f52bc5cb2`

Declared capabilities: `os.nixos`, `tool.systemd`, `tool.coreutils`, `tool.sudo`, `tool.nixos-rebuild`.

1. [ ] **NOT RUN / PENDING live acceptance:** Validate offline and against the intended read-only profile (offline passed; provider-aware NOT RUN).
2. [ ] **NOT RUN / PENDING live acceptance:** Start from a fresh compatible template.
3. [ ] **NOT RUN / PENDING live acceptance:** Complete every lesson and verification in order.
4. [ ] **NOT RUN / PENDING live acceptance:** Intentionally fail a check and assess remediation.
5. [ ] **NOT RUN / PENDING live acceptance:** Save/exit mid-lesson and resume at the first incomplete check.
6. [ ] **NOT RUN / PENDING live acceptance:** Confirm expected cumulative course state.
7. [ ] **NOT RUN / PENDING live acceptance:** Destroy through LearnLab and verify absence.
8. [ ] **NOT RUN / PENDING live acceptance:** Record certification only after successful cleanup or reconciliation.
