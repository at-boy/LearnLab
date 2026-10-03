# LearnLab roadmap status

Updated 2026-10-04. Paused for user-requested usage headroom; last check 88% used (12% remaining), reset October 4 05:13 Europe/Copenhagen. Roadmap is NOT complete. Active workspace: /home/at-boy/.codex/worktrees/learnlab-roadmap/LearnLab, branch codex/learnlab-roadmap. Original branches/worktrees unchanged.

Latest offline checkpoint: 661 passed, 1 deselected; Ruff and mypy passed. Debian Task 1 commit 5b1654c awaits independent review. Bootstrap integration review approved the TLS correction and provenance; final one-line assertion maintenance remains for scoped review. No merge approval requested yet.

## Authority and boundaries

Execute the currently planned roadmap using sub-agents, TDD and independent review gates. This task explicitly authorizes offline implementation of existing specs/plans. Ask before merging, pushing or live infrastructure operations. Preserve every branch/worktree and the untracked top-level collections/ tree. Only current-content, exact-digest live evidence can certify a course. Historical observations, offline tests and self-attestation cannot.

Reconciled against the September 24 final roadmap response in task 01a08774-edbf-7431-9dc7-e3e33d70c589 (retrieved live on October 3), repository specs/plans, completion reports and two independent read-only sub-agent audits.

## Verified local inventory

Remote names below are local tracking refs; no network fetch was performed.

| Branch | Tip | Relation to main | Worktree status |
|---|---|---|---|
| main | 0da669f | Current base; matches origin/main | Only pre-existing untracked collections/ before this checkpoint |
| feature/course-authoring-validation | 09fe71f | Contained in main | Clean |
| feature/minimal-terminal-vertical-slice | 8b0e2a7 | Contained in main | Clean |
| interactive-course-sessions | b8b7c7f | Contained in main | Clean |
| feature/pending-course-certification | 287d350 | Contained in main | Clean |
| feature/nixos-template-course | 7ae9939 | 27 commits absent from main; main has one merge commit absent from branch | Clean |

All five feature worktrees remain under .worktrees/. Bootstrap work is at .worktrees/template-bootstrap-course. All six local tips match their corresponding local origin tracking refs.

## Delivery and acceptance sequence

| Order | Workstream | Actual status and next gate |
|---|---|---|
| 1 | Integrate NixOS/provider-bootstrap work | Existing implementation and historical scoped reviews; fresh branch gate now passes 657 non-live tests, Ruff and mypy. Whole-diff review finished; P2 TLS handoff correction and provenance approved. Finish scoped review of final assertion change, then request merge/push approval for exact reviewed refs. No merge has happened. |
| 2 | Bootstrap acceptance | NixOS and provider-bootstrap remain draft. Prepare exact resource scope and request live authorization. Complete current-digest traversal, recovery, identity/permissions, lifecycle and cleanup evidence before registry changes. |
| 3 | Debian 13 template | Task 1 entry course implemented at 5b1654c with real RED/GREEN and CLI isolation; independent task review pending. Tasks 2–5 remain, including guide, wheel coverage and acceptance report. Two-clone live acceptance separately authorized. |
| 4 | Existing-course certification | Six nginx/nftables/systemd courses have offline corrections but remain draft. Live failure/remediation, save/resume, cumulative state and teardown on each OS remain. Excluded NAT lessons remain blocked pending real multi-machine ingress; this does not block the other nftables lessons. |
| 5 | Discovery/continuation | Planned, unimplemented. Offline listings/progress, continue and interactive home. |
| 6 | Interactive secret resolution | Planned, unimplemented. Shared resolver, hidden prompt, explicit stdin, cancellation/redaction and integration including continue. Coordinate with discovery. |
| 7 | NixOS administration | Planned, unimplemented. Metadata/prerequisites/revision/hints first, then Administration Foundations, Nix Language and Store, Flakes and Fleet. Reconcile proposed maturity metadata with existing digest certification; live gates separately authorized. |
| 8 | Multi-machine/networking | Planned, unimplemented. Single-VM normalization, multi-VM shared network, machine checks/jump SSH, operator-managed isolated pools, managed ephemeral SDN. Recovery and cleanup at each stage; live mutations require approval. |
| 9 | Roadmap closure | Whole-branch integration review, packaging/compatibility, remaining live gates and exact-digest certification, reports and authorized integration. Explicitly revisit NAT content and acceptance. |

This is delivery order, not a strict dependency chain. Continue independent offline work while live acceptance is blocked.

## Evidence and stale documentation

Canonical plans/specs are docs/superpowers/plans/ and specs/. Provider-bootstrap additions are available on the newer bootstrap branch. Its reports are docs/course-validation/2026-09-10-nixos-template.md and 2026-09-11-proxmox-provider-bootstrap.md; existing-course report is 2026-09-08-pending-courses.md. Historical correction review ledger is .worktrees/template-bootstrap-course/.superpowers/sdd/2026-09-14-nixos-live-corrections/progress.md.

The template task index docs/superpowers/tasks/2026-09-10-template-bootstrap.md incorrectly calls NixOS unimplemented. The provider-bootstrap spec header also predates implementation. Reconcile these on the execution branch. Both main and the bootstrap branch have an empty certifications registry. No status has been upgraded to live-certified.

## Resume precisely here

1. Check fresh account usage. Read this file, execution-log.md and the Debian per-plan ledger. Stop new work earlier (around 70% used) to leave room for review/checkpoint; simultaneous agents consumed usage faster than expected.
2. Use existing native worktree /home/at-boy/.codex/worktrees/learnlab-roadmap/LearnLab and branch codex/learnlab-roadmap. Do not create another or modify preserved branches. Root docs/roadmap is a pointer/snapshot only.
3. Independently review Debian Task 1 range 7ae9939..5b1654c using its brief/report; no Task 2 until it passes. Latest full gate supersedes the transient provider-report failures honestly recorded in implementer's report.
4. Review the final one-line provider report assertion update (Current-digest -> Historical), then record integration gate for exact current commits. Original bootstrap whole-diff review and TLS/provenance re-review are in bootstrap-integration-review.md. No remaining product finding there. Request merge/push approval with exact reviewed refs when ready; do not infer approval.
5. Continue Debian Tasks 2–5 sequentially with TDD and task reviews; then discovery/continuation, secret resolution, administration and multi-machine as existing plans prescribe. Maintain per-plan ledgers, reports and this log. Live gates are independent blockers, not a reason to stop offline work.
6. Use live-acceptance-gates.md to prepare privately selected exact resources and effects before requesting live authorization. Current resources/profile/independent reconciler are not selected. All certifications remain draft.

No merge/push/live approval obtained. No automatic resume or reset-credit redemption scheduled. Native workspace shares the existing .venv via an untracked symlink; use PYTHONPATH=src and python -m, never stage that symlink. Root collections/ remains untouched.
