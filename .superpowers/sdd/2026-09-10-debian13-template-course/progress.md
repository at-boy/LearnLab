# SDD ledger — plan: docs/superpowers/plans/2026-09-10-debian13-template-course.md

2026-10-04: Resume authorized. Workspace codex/learnlab-roadmap at bootstrap tip 7ae9939; no merge. User usage pause threshold: check each task/review, stop new dispatch by 80% used and checkpoint by 85%.

## Preflight reconciliation

| Task/pair | Produces/consumes or internal check | Finding/ruling |
|---|---|---|
| 1 | Real first lesson; NONE CLI start/resume | Existing shared metadata already handles NONE; preserve it. |
| 2 | Install/access lessons and guide; consumes helpers from 1 | Content-token samples are weak; use real catalog/validator behavior and explicit editorial review for prose. |
| 3 | Seal/clone lessons; consumes 1 helpers and 2 access | Test any executable guards via stubs; manual instructional actions remain unexecuted. |
| 4 | Final lesson, guide, packaging | Extend existing wheel build once; existing bootstrap checks retained. |
| 5 | Full offline gate and report | Live steps conditional on separate authorization; do not check them offline. |
| 1/2, 1/3, 1/4 | Shared course test helpers/manifest | Append only complete lessons; stable IDs. |
| 2/3, 2/4, 3/4 | Guide and cumulative course manifest | Sequential implementers; no concurrent edits. |
| 1/4 | CLI no-profile regression | Extend rather than duplicate isolated startup/resume flow. |
| 1/5, 2/5, 3/5, 4/5 | Final evidence consumes all task outputs | Recompute course digest after final changes; do not certify. |

Ruling: Build atop the preserved bootstrap tip while its merge is awaiting approval, because this includes completed corrections without mutating main or preserved refs. Current main differs by merge history only; verify full integration separately.
Ruling: Existing written specs/plans are authorized by explicit finish-roadmap request. No new design scope. Use behavioral tests for runnable contracts; prose inspection records editorial coverage, not guest correctness.

Task 1: pending; base to be recorded before dispatch.

Task 1: implementation committed 5b1654c; base 7ae9939. Report task-1-report.md. Independent task review PENDING; do not mark complete or start Task 2. Controller final full offline gate 661 passed/1 deselected, Ruff/mypy clean after bootstrap provenance correction. Pause at usage 88%; resume by dispatching Task 1 reviewer with fixed range and report.

Task 1: complete — 7ae9939..5b1654c independently reviewed; spec and quality PASS in task-1-review.md. Final controller regression gate 661 passed/1 deselected, Ruff/mypy clean.
Provider assertion disposition: PASS; no remaining actionable bootstrap integration findings.
Task 2: in progress — base 3d4b14d; implementer debian_task2; task-2-brief.md and task-2-report.md.

Task 2: implemented 3d4b14d..3e5da80; report task-2-report.md (committed). RED 2 missing lessons, GREEN 4 focused, full offline 663 passed/1 deselected; catalog no findings. Independent review debian2_review in progress.

Task 2: review spec PASS / quality NEEDS FIXES. task-2-review.md: P1 concrete disposable-lab sudoers rule and verification; P2 named-account lookup and concrete authenticated SSH enrollment. Fix round 1 dispatched to original implementer; no Task 3 until re-review passes.

Task 2: complete — initial 3e5da80; fixes 0140b92 and f90c648. Final independent spec PASS / quality PASS in task-2-review.md. Initial full offline 663 passed/1 deselected; after instructional fixes focused4 passed and catalog no findings; final SSH options checked locally with ssh -G -F /dev/null, no network. No open findings.
Task 3: pending — brief task-3-brief.md already extracted; start from current branch after reading ledger. Tasks 4–5 also pending. Pause for usage headroom after gate; no new implementation dispatched.

2026-10-04 third resume: user authorized continuing with usage watch; initial5-hour0%, weekly44%. Task3 in progress, base a9e8afa, implementer debian_task3, report task-3-report.md. Stop new dispatch near70%, checkpoint before exhaustion.

Task3: implemented a9e8afa..5eab41f. RED3 missing-lesson failures; focusedGREEN5, full664 passed/1 deselected, validator no findings, Ruff no-cache and staged whitespace clean. task-3-report.md committed. Independent review debian3_review in progress; not complete until spec/quality gate passes.

Task3: review found P1 D-Bus regular-file identity disposition and P2 SSH boot activation after socket disable. task-3-review.md has both Changes requested verdicts. Original implementer fixed both in5a34e98, parent5eab41f; report appended. Focused5 passed, catalog no findings, staged whitespace clean; no full-suite rerun after instructional fixes. Scoped re-review PENDING — next action on resume. Review package review-5eab41f..5a34e98.diff prepared. Do not mark Task3 complete or start Task4 yet.
Usage pause:82% used at last check, reset October4 21:31 Europe/Copenhagen. All agents stopped; no new implementation/review dispatch.
