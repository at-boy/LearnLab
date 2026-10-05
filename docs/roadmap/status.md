# LearnLab roadmap status

October 5 continuation: Debian offline implementation and final independent review passed. Immutable checkpoint026fb27 passed 666 offline tests, 1 live deselected. Course revision7d696d4 has digest b8b37477effe6444331d9a9e3c6a5398ec800eb3be7e05927b08ca2f8423c995. Course remains draft; all live gates pending. Roadmap is NOT complete.

Active workspace: /home/at-boy/.codex/worktrees/learnlab-roadmap/LearnLab, branch codex/learnlab-roadmap. Main remains3159e18 from the approved checkpoint; later work is local and unmerged. All branches/worktrees preserved. Discovery Task1 read-only progress projection is in progress, independently of Debian integration. Latest usage70% five-hour and83% weekly; finish current checkpoint/review before pausing.

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
| 3 | Debian 13 template | Seven-lesson course, guide, packaging/CLI coverage and acceptance report complete offline. Tasks1–5 and final independent review passed; current-content full gate666 passed/1 live deselected. Merge/push approval and exact-digest live acceptance remain separate gates. |
| 4 | Existing-course certification | Six nginx/nftables/systemd courses have offline corrections but remain draft. Live failure/remediation, save/resume, cumulative state and teardown on each OS remain. Excluded NAT lessons remain blocked pending real multi-machine ingress; this does not block the other nftables lessons. |
| 5 | Discovery/continuation | Task1 read-only progress projection in progress. Remaining: offline listings/progress, continue and interactive home. |
| 6 | Interactive secret resolution | Planned, unimplemented. Shared resolver, hidden prompt, explicit stdin, cancellation/redaction and integration including continue. Coordinate with discovery. |
| 7 | NixOS administration | Planned, unimplemented. Metadata/prerequisites/revision/hints first, then Administration Foundations, Nix Language and Store, Flakes and Fleet. Reconcile proposed maturity metadata with existing digest certification; live gates separately authorized. |
| 8 | Multi-machine/networking | Planned, unimplemented. Single-VM normalization, multi-VM shared network, machine checks/jump SSH, operator-managed isolated pools, managed ephemeral SDN. Recovery and cleanup at each stage; live mutations require approval. |
| 9 | Roadmap closure | Whole-branch integration review, packaging/compatibility, remaining live gates and exact-digest certification, reports and authorized integration. Explicitly revisit NAT content and acceptance. |

This is delivery order, not a strict dependency chain. Continue independent offline work while live acceptance is blocked.

## Evidence and stale documentation

Canonical plans/specs are docs/superpowers/plans/ and specs/. Provider-bootstrap additions are available on the newer bootstrap branch. Its reports are docs/course-validation/2026-09-10-nixos-template.md and 2026-09-11-proxmox-provider-bootstrap.md; existing-course report is 2026-09-08-pending-courses.md. Historical correction review ledger is .worktrees/template-bootstrap-course/.superpowers/sdd/2026-09-14-nixos-live-corrections/progress.md.

The template task index is reconciled on the execution branch. Historical provider-bootstrap spec/plan status headers still predate implementation; read completion reports and this ledger for actual status. Both main and the bootstrap branch have an empty certifications registry. No status has been upgraded to live-certified.

## Resume precisely here

1. Check both fresh five-hour and weekly usage. Read this file, execution-log.md and Debian per-plan progress.md. Reserve room for reviews/checkpoint; never consume reset credits implicitly.
2. Reuse this worktree/branch. Only untracked .venv expected; use PYTHONPATH=src and python -m to bind the shared interpreter to local source. Do not reimplement reviewed Tasks 1–4.
3. Debian final review is PASS after the remote sudo correction; full immutable026fb27 regression gate passed. Do not repeat completed reviews or certify from offline tests. Request exact-checkpoint merge/push approval; the old approval covered only3d4b14d, already published as3159e18.
4. Finish discovery Task1 and independent review, preserving a precise checkpoint if usage requires stopping. Use its per-plan ledger and report; no CLI work before the projection review gate.
5. Continue remaining offline roadmap: discovery/continuation, secret resolution, NixOS administration, staged multi-machine networking. Bootstrap/existing-course live certification remains independently blocked on current-content evidence and explicit resource authorization.
6. Prepare exact private resource/cleanup scope before requesting live approval. All live checkpoints remain NOT RUN; never infer certification from historical, offline or self-attested evidence.

Main's published roadmap docs reflect the earlier approved checkpoint; this branch is the current execution authority. Original root collections/ untouched; original audit snapshot retained at .worktrees/roadmap-audit-snapshot-20261004. No automatic resume or reset redemption scheduled.
