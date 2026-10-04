# LearnLab roadmap status

Updated 2026-10-04 after third resumed batch. Paused at82% five-hour usage (18% remaining at last check); reset October4 21:31 Europe/Copenhagen. Roadmap is NOT complete.

Active workspace: /home/at-boy/.codex/worktrees/learnlab-roadmap/LearnLab, branch codex/learnlab-roadmap. Main remains3159e18 from the previously approved/pushed checkpoint. Later work remains local; all original branches/worktrees preserved.

Debian Tasks1–2 independently PASS. Task3 implementation5eab41f passed full offline664 tests/1 deselected. Review found two correctness gaps; fixes5a34e98 passed focused5 tests and catalog validation, but independent scoped re-review is PENDING. No full-suite rerun after those instructional fixes. Tasks4–5 not started. No live operations or certification.

## Authority and boundaries

Execute the currently planned roadmap using sub-agents, TDD and independent review gates. This task explicitly authorizes offline implementation of existing specs/plans. Ask before merging, pushing or live infrastructure operations. Preserve every branch/worktree and the untracked top-level collections/ tree. Only current-content, exact-digest live evidence can certify a course. Historical observations, offline tests and self-attestation cannot.

Reconciled against the September 24 final roadmap response in task 01a08774-edbf-7431-9dc7-e3e33d70c589 (retrieved live on October 3), repository specs/plans, completion reports and two independent read-only sub-agent audits.

## October 3 baseline inventory (historical; superseded for main below)

Remote names below are local tracking refs; no network fetch was performed.

| Branch | Tip | Relation to main | Worktree status |
|---|---|---|---|
| main | 0da669f | Current base; matches origin/main | Only pre-existing untracked collections/ before this checkpoint |
| feature/course-authoring-validation | 09fe71f | Contained in main | Clean |
| feature/minimal-terminal-vertical-slice | 8b0e2a7 | Contained in main | Clean |
| interactive-course-sessions | b8b7c7f | Contained in main | Clean |
| feature/pending-course-certification | 287d350 | Contained in main | Clean |
| feature/nixos-template-course | 7ae9939 | 27 commits absent from main; main has one merge commit absent from branch | Clean |

All five feature worktrees remain under .worktrees/. Bootstrap work is at .worktrees/template-bootstrap-course. At that baseline all six local tips matched their local origin tracking refs. On October 4 main advanced to 3159e18 and its remote tip was verified; codex/learnlab-roadmap is the new preserved execution branch.

## Delivery and acceptance sequence

| Order | Workstream | Actual status and next gate |
|---|---|---|
| 1 | Integrate NixOS/provider-bootstrap work | Existing implementation and historical scoped reviews; fresh branch gate now passes 657 non-live tests, Ruff and mypy. Whole-diff review finished; P2 TLS handoff correction and provenance approved. Final assertion review passed. Approved checkpoint 3d4b14d merged and pushed as main 3159e18; remote verified. Original branch/worktree retained. |
| 2 | Bootstrap acceptance | NixOS and provider-bootstrap remain draft. Prepare exact resource scope and request live authorization. Complete current-digest traversal, recovery, identity/permissions, lifecycle and cleanup evidence before registry changes. |
| 3 | Debian 13 template | Tasks 1–2 complete with independent reviews: intro, installer, installation and lab access lessons plus partial guide. Task3 sealing/two-clone lessons implemented with review corrections; scoped re-review pending. Tasks4–5 remain: profile handoff, complete guide, wheel coverage and acceptance report. Two-clone live acceptance separately authorized. |
| 4 | Existing-course certification | Six nginx/nftables/systemd courses have offline corrections but remain draft. Live failure/remediation, save/resume, cumulative state and teardown on each OS remain. Excluded NAT lessons remain blocked pending real multi-machine ingress; this does not block the other nftables lessons. |
| 5 | Discovery/continuation | Planned, unimplemented. Offline listings/progress, continue and interactive home. |
| 6 | Interactive secret resolution | Planned, unimplemented. Shared resolver, hidden prompt, explicit stdin, cancellation/redaction and integration including continue. Coordinate with discovery. |
| 7 | NixOS administration | Planned, unimplemented. Metadata/prerequisites/revision/hints first, then Administration Foundations, Nix Language and Store, Flakes and Fleet. Reconcile proposed maturity metadata with existing digest certification; live gates separately authorized. |
| 8 | Multi-machine/networking | Planned, unimplemented. Single-VM normalization, multi-VM shared network, machine checks/jump SSH, operator-managed isolated pools, managed ephemeral SDN. Recovery and cleanup at each stage; live mutations require approval. |
| 9 | Roadmap closure | Whole-branch integration review, packaging/compatibility, remaining live gates and exact-digest certification, reports and authorized integration. Explicitly revisit NAT content and acceptance. |

This is delivery order, not a strict dependency chain. Continue independent offline work while live acceptance is blocked.

## Evidence and stale documentation

Canonical plans/specs are docs/superpowers/plans/ and specs/. Provider-bootstrap additions are available on the newer bootstrap branch. Its reports are docs/course-validation/2026-09-10-nixos-template.md and 2026-09-11-proxmox-provider-bootstrap.md; existing-course report is 2026-09-08-pending-courses.md. Historical correction review ledger is .worktrees/template-bootstrap-course/.superpowers/sdd/2026-09-14-nixos-live-corrections/progress.md.

The template task index is reconciled on the execution branch. Historical provider-bootstrap spec/plan status headers still predate implementation; read completion reports and this ledger for actual status. Both main and the bootstrap branch have an empty certifications registry. No status has been upgraded to live-certified.

## Resume precisely here

1. Check fresh usage. Read this file, execution-log.md and Debian per-plan progress.md. Stop new implementation near70% used; preserve room for reviews/checkpoint and never redeem reset credits implicitly.
2. Reuse this native worktree/branch. Only untracked .venv is expected (shared interpreter, never stage). Use PYTHONPATH=src and python -m; the unqualified installed CLI can import the sibling checkout.
3. Next action: scoped independent Task3 re-review of5eab41f..5a34e98 against task-3-review.md's two findings. Package review-5eab41f..5a34e98.diff and amended task-3-report.md are ready. Verify the corrected D-Bus identity and SSH boot-activation paths in lesson, guide and clone acceptance. Do not redo the broad review or claim complete until both verdicts pass.
4. After Task3 gate passes, execute Task4 from task-4-brief.md (already extracted): profile handoff, finished guide, README/wheel/CLI coverage. Then Task5 offline acceptance report/final review, retaining draft status unless separately authorized current-digest live acceptance passes.
5. Continue remaining authorized offline workstreams (discovery, secrets, administration, multi-machine) while live acceptance is blocked. Maintain per-task reports, spec/quality review gates and durable logs.
6. Merge/push approval covered ONLY3d4b14d, fulfilled as remote main3159e18. Request new approval for later commits, preserve every branch/worktree. Live scope is not selected or authorized; prepare exact private resource/cleanup scope first. Historical/offline/self-attested evidence never certifies current content.

Main's published roadmap documents are the older approved checkpoint; this branch is the current execution authority. No automatic resume/reset-credit redemption scheduled. Root collections/ untouched; original audit snapshot retained at .worktrees/roadmap-audit-snapshot-20261004.
