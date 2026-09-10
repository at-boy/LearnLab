# Task 6 — offline acceptance coverage and live blockers

Date: 2026-09-10. Status: offline scope complete; live Steps 1–3 remain pending.
No provider-aware validation, provider call, SSH, provisioning or destruction
occurred. No scratch profile was selected or destructive-test authorization
received. Certification registry remains exactly `certifications: []`.

## Scope and implementation

Read the Task 6 brief, approved design and Tasks 2–4 implementation/review reports.
Controller explicitly extended the offline scope to shipped metadata and installed
wheel integration coverage. Added data-driven loading tests across all seven
shipped courses, matching catalog summary maturity and nonempty unique capability
metadata. Assert the exact six pending paths and their draft status. Extended the
existing wheel build/install smoke test to require the bundled manifest, load all
six pending courses, inspect draft/capability metadata, and exercise each installed
start gate with fail-fast state/settings sentinels. Existing installed CLI offline
validation continues to cover the entire packaged catalog.

Created `docs/course-validation/2026-09-08-pending-courses.md` with six canonical
course digests and capability sets, correction summaries and precise family live
blockers. Each course has its own eight-step NOT RUN/PENDING live checklist.
The September 8 filename is retained as the workstream identifier; the actual
offline review date is September 10. Declared requirements and digest snapshots
are explicitly not certificates. No personal infrastructure data was recorded.

Updated plan Tasks 1–5 checkboxes following controller-confirmed clean reviews;
Task 6 Step 4 is checked, Steps 1–3 remain unchecked with the operator gate.
The recorded commit wording describes offline verification, not certification.

## Verification evidence

All commands ran in the pending-course-certification worktree using the main
checkout's `/home/at-boy/Projects/codex/LearnLab/.venv/bin/` tools.

- `python -m pytest tests/test_shipped_course_metadata.py tests/test_packaging.py -q`:
  **10 passed in 2.70s**, including actual wheel build and pip target installation.
- `python -m pytest -m 'not live' -q`: **493 passed, 1 deselected in 31.51s**.
  Full output: `/tmp/task6-full.log`. This includes the wheel smoke after the
  embedded-script formatting correction.
- `ruff check .`: **All checks passed!** Initial run reported two E501 lines
  in the embedded wheel smoke script; changed its context manager to parenthesized
  multiline syntax and reran the full Ruff gate successfully.
- `mypy src`: **Success: no issues found in 17 source files**.
- `PYTHONPATH=src learnlab validate`: exit 0; three existing warnings confined to
  `proxmox/proxmox-admin` (deprecated requirements, missing OS capability,
  redundant manual confirmation). No pending-course findings.
- Invoked the actual CLI app with `CliRunner` for each of the six `validate PATH`
  commands under `PYTHONPATH=src`: each exit 0, **Validation passed with no findings.**
- `git diff --check`: passed; staged check performed before commit.

These new tests are characterization/integration coverage of already implemented
behavior. Their first run passed; no artificial RED or production change is
claimed. Digests are calculated for the report, not pinned in brittle tests.

## Self-review and remaining gates

Reviewed the added tests, installed resource provenance, all six digest/capability
entries, per-course checklists, plan status and staged file allowlist. Curriculum
and empty certification registry were not modified. No push or merge performed.
Offline tests cannot prove evaluated guest configuration or actual cleanup.

Operator must select scratch profiles and explicitly approve the exact course,
compatible template capabilities and cleanup before any live work. Execute each
protocol serially, destroy through LearnLab and verify absence. Failed or uncertain
cleanup blocks certification until reconciled; deletion by VMID alone is forbidden.
Only successful exact-digest live acceptance may produce a registry record.
