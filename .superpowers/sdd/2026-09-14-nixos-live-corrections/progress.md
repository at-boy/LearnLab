# SDD ledger — bounded design: NixOS live-discovered identity and boot corrections

Authority: `docs/superpowers/specs/2026-09-10-nixos-template-course-design.md`
Plan: `docs/superpowers/plans/2026-09-10-nixos-template-course.md`
Implementation base: `3bb629d697b530d2948265affd74ea2c6a5ceddf`
Workspace: `/home/at-boy/Projects/codex/LearnLab/.worktrees/template-bootstrap-course`

Approved design: require a stopped VM before post-install boot-order mutation; derive each clone's four-byte `/etc/hostid` from its freshly generated `/etc/machine-id` without a static `networking.hostId`; seal machine-id, hostid, and exact configured SSH host-key pairs; prove cross-clone distinctness and per-clone reboot stability.

Ruling: the first-boot hostid service is appropriate for this ext4 course template and runs after machine-id availability before multi-user completion. It fails closed on absent/malformed machine-id, writes a same-filesystem temporary four-byte file, then atomically installs `/etc/hostid`. It is not presented as a ZFS boot design. Cost if wrong: services needing hostid earlier than multi-user would require an earlier unit; the shipped course does not use ZFS or such a service.

Task 1: complete — commit `29d756d` (`3bb629d..29d756d`), independent spec and quality review clean. RED 14 failed/27 passed; focused 60 passed; related 189 passed; full non-live 625 passed, 1 deselected; validator, Ruff, mypy, changed-file formatting and whitespace clean. Nix evaluation/live behavior remains pending.
Task 2: pending — revised offline/live report after course bytes and live acceptance stabilize.

Task 3: complete — add a QGA sealing alternative for console-paste failure without
weakening console recovery or candidate-SSH trust boundaries. The QGA preflight
requires revalidated candidate identity/layout and effective `sshd -G -T` ports/
host-key paths; the deliberate request stops all SSH listeners/sessions/processes
(including `sshd-session`), validates exact files, seals them, syncs, requests
poweroff and requires positive Proxmox Stopped state. Failure, partial/uncertain
output or interruption requires reconciliation, never a blind rerun. No rebuild,
restart, reboot, conversion, force flag, glob or recursive deletion was added.
RED: focused QGA regression failed 2/2 because the sealing fallback was absent.
GREEN: 70 course tests passed; offline validation, Ruff and `git diff --check`
passed. Live QGA/guest/Proxmox behavior remains pending explicit authorization.

Fix round 1 for `fb896d8`: replace the QGA prose-token regression with isolated
execution of the actual embedded mutation shell, with stubs and mutation logs.
RED: 6 unsafe cases reached destructive continuation (active `sshd`, `sshd` or
`sshd-session` process, failed `ss`, reappearing hostid or host key); 10 other
guard fixtures already failed closed. The revised identical course/guide script
uses explicit named error branches, preserves `ss` exit status separately from
its output, and verifies empty/absent sealed postconditions including dangling
links before `sync` or poweroff. GREEN: focused QGA execution suite 16 passed;
course suite 84 passed; validator, Ruff and `git diff --check` passed. Live QGA/
guest/Proxmox behavior remains pending explicit authorization.

Task 4: complete — incorporated two Stage 7 live-discovered command-environment
facts with TDD. The QGA preflight now exports the exact target-generation
`NIX_PATH` before `nixos-option` and treats a missing target path as a stop and
reconciliation condition. The identical course/guide sealing mutation matches
only `port`/`hostkey` keywords case-insensitively and preserves original values,
including mixed-case paths. RED: the focused regressions failed 3/3 because both
preflights lacked `NIX_PATH` and mixed-case SSHD output produced no ports. GREEN:
focused regressions passed 3; the course suite passed 87; validator, focused Ruff
and `git diff --check` passed. Alternate channel layouts still require documented
local reconciliation; no live operations or certification updates were made.
Independent task review for `93984d1..4506174`: spec compliance approved and
task quality approved with no Critical, Important or Minor findings. Reviewer
confirmed the exact preflight path export, value-preserving case-insensitive
parsing, executable mixed-case regression and unchanged report/registry scope.

Task 5: in progress — teach the Python 3.13 strict-verification failure mode and
the bounded, out-of-band-authenticated leaf-pin fallback consistently in the
provider-bootstrap and NixOS provider-handoff surfaces. No provider code/schema,
live operation, certification, user configuration, merge or push is in scope.

Preflight interaction table:

| Surfaces | Producer and consumer relationship | Finding |
| --- | --- | --- |
| Provider lessons 04 and 05 | Profile lesson establishes trust/process inputs; health lesson consumes them | Must distinguish the token-secret environment name from `SSL_CERT_FILE` and carry cleanup/rotation rules into the health shell. |
| NixOS lesson 06 and guide | Course handoff and standalone guide teach the same operator flow | Must remain semantically identical while the guide may contain the fuller command example. |
| README and both courses | README is generic schema guidance consumed before either course flow | Existing private-lab `tls_verify = false` support must not be presented as this course's remediation; retain schema truth while making the secure course path explicit. |
| Tests and learner surfaces | Focused content contracts guard the security-relevant instructional behavior | Existing repository tests intentionally treat safety wording as curriculum contract; tests must fail before the new guidance is added. |
| Task 5 internally | Requirements, files, tests and commit scope | Consistent; no production API or live state is required. |

Ruling: retain the repository's existing curriculum-content test style for this
security-sensitive human procedure, despite the general preference not to test
ordinary prose. Here the packaged curriculum text is the shipped behavior and
the plan already establishes content-contract regressions. Cost if wrong: the
tests may need updating for a future equivalent rewrite, but they prevent silent
loss of the fail-closed trust boundary now.

Task 5: complete — added focused cross-surface regressions and consistent
strict-TLS recovery guidance to provider-bootstrap lessons 04/05, NixOS lesson
06 and its standalone guide, and README provider configuration. The preferred
repair remains a correctly issued controller-trusted certificate; the bounded
leaf-pin fallback requires separate-path authentication, issuer/chain, exact
SAN, validity-window and SHA-256 fingerprint checks, owner-only storage,
process-scoped `SSL_CERT_FILE`, explicit cleanup and fail-closed rotation.
`token_secret_env` remains only the token-secret environment-variable name;
there is no new profile field or provider-code change. RED: 3 focused tests
failed because the guidance was absent. GREEN: 3 focused tests and 126 affected
course tests passed; both target validators, focused Ruff and `git diff --check`
passed. Course-digest reports were refreshed without changing draft status or
the certification registry. No live/network operation, user-config access,
certification, merge or push occurred.
