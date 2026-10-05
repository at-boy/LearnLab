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

Fourth resume: initial5-hour0%, weekly59%. Task3 scoped re-review PASS spec/quality; both findings addressed in5a34e98. Task3: complete (offline instructional scope). Task4 in progress, base0e25093, implementer debian_task4, report task-4-report.md. No live certification.

Task4: implemented0e25093..51a6525. RED2 missing-final-lesson/order; focused8, installed-wheel2, full666 passed/1 deselected, catalog no findings, focusedRuff and staged diff clean. task-4-report.md committed. Independent review debian4_review active.

Task4: complete —51a6525 independent spec/quality PASS in task-4-review.md, no findings.
Task5: offline report in progress, base51a6525, implementer debian_task5. Ruling: reuse exact-content fresh Task4 full666/wheel2/focused8 evidence with explicit revision/provenance; run missing checks/digest, no redundant full suite without content changes. Final whole-course review remains a separate pending gate. Usage64% at dispatch.

Task5: offline report implemented c556dfa; course content revision51a6525, digest8c815d9f0c3df55d0089f2a34c69d18c5cc89c467ed61fc99f14899dda2ce1af. Fresh Ruff no-cache/mypy17/catalog/whitespace passed; Task4 regression results reused with explicit provenance and unchanged content. Task5 final review gate PENDING; do not mark plan complete.
Final whole-course review is next: final-course-review.diff (7ae9939..c556dfa excluding only process logs/.superpowers), linked spec/plan, acceptance report and task reports. Reviewer should cover final integrated course and Task5 evidence together, not repeat each prior review. No final reviewer dispatched in this window.
Pause usage83%5-hour,71%weekly; reset October5 02:37 Europe/Copenhagen. Tasks1–4 complete, Task5 pending final review; all live checkpoints pending.

2026-10-05: Final P2 remote sudo correction7d696d4, evidence026fb27. Independent final re-review PASS spec/quality. Immutable026fb27 snapshot full666 passed/1 live deselected (42.08s). Task5 complete for offline outcome; live traversal remains pending, registry unchanged.
