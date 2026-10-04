# LearnLab roadmap status

Updated 2026-10-04 after second resumed batch. Paused for usage headroom (79% used at last pre-checkpoint reading; later exact reading recorded in execution log). Reset reported October 4 15:41 Europe/Copenhagen. Roadmap is NOT complete.

Active workspace: /home/at-boy/.codex/worktrees/learnlab-roadmap/LearnLab, branch codex/learnlab-roadmap. Main checkpoint 3d4b14d was explicitly approved, merged and pushed as 3159e18; remote verified. All branches/worktrees retained. Later Task 2 commits remain unmerged/unpushed.

Debian Task 1 and Task 2 independently PASS (spec and quality). Task 2 content tip f90c648 follows 3e5da80 and 0140b92. Latest full suite before instructional fixes: 663 passed, 1 deselected. After fixes: 4 focused tests passed, course validation no findings, SSH options verified offline. All courses remain draft; no live operations.

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
| 3 | Debian 13 template | Tasks 1–2 complete with independent reviews: intro, installer, installation and lab access lessons plus partial guide. Tasks 3–5 remain: sealing, two-clone identity acceptance, profile handoff, complete guide, wheel coverage and acceptance report. Two-clone live acceptance separately authorized. |
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

1. Check fresh usage and read execution-log.md plus the Debian per-plan ledger. Stop new implementation around 70% used, allow review/checkpoint headroom, and never redeem credits implicitly.
2. Reuse this native worktree/branch; do not create another or reimplement Tasks 1–2. Only untracked .venv is expected (shared interpreter, never stage it). Use PYTHONPATH=src and python -m.
3. Task 3 next: read existing task-3-brief.md and linked Debian spec; implement sealing and two-clone identity lessons with TDD and independent review. No live execution. Then Tasks 4–5 (handoff/guide/wheel and honest offline acceptance).
4. Continue other existing offline workstreams while live gates are blocked: discovery/continuation, secret resolution, NixOS administration, staged multi-machine networking. Maintain reports and both spec/quality review gates.
5. Approval for merge/push covered ONLY 3d4b14d and was fulfilled as remote main 3159e18. Ask before merging or pushing later commits. Preserve all refs/worktrees. Current root collections/ remains untouched; original root audit snapshots retained at .worktrees/roadmap-audit-snapshot-20261004.
6. Live resource scope has not been selected or authorized. Prepare exact private resource/cleanup scope using live-acceptance-gates.md before asking. Never certify from historical, offline or self-attested evidence.

No automatic resume or reset-credit redemption scheduled. Main's published roadmap documents are the earlier approved checkpoint; this branch's status and execution log are the current authority.
