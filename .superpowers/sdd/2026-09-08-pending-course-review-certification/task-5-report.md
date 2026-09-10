# Task 5 — course authoring guide report

Status: implemented and offline verified; no live certification performed.

## Documentation changes

Revised the authoring guide to describe the implemented canonical curriculum
and certification workflow. It now defines `draft`, `offline-validated`, and
`live-validated`; the complete course-tree SHA-256 digest; the strict
non-secret certification record; guest capability review; offline,
provider-read-only, and live validation boundaries; version and progress
consequences; and the eight-point live acceptance checklist. The checklist
requires explicit approval for an exact course and scratch profile, an
intentional failed check, mid-lesson resume, cumulative-state review, LearnLab
teardown, absence verification, and reconciliation of uncertain cleanup before
certification.

The nested-virtualization walkthrough is explicitly illustrative and
uncertified. The six pending nginx, nftables, and systemd courses are described
as canonical drafts because live acceptance has not been performed. nftables
NAT remains deliberately deferred to the multi-machine workstream.

Updated README start guidance for the current empty certification registry:
the Proxmox example, like every other unproven course, uses
`--include-drafts`, with a notice that the flag is an opt-in rather than proof.
No certification record was added or changed.

## TDD and verification evidence

All commands ran in the pending-course-certification worktree with
`PYTHONPATH=src` where required and the main checkout's absolute `.venv` tools.

- Initial focused RED:
  `python -m pytest -q tests/test_course_authoring_docs.py` produced
  **4 failed, 1 passed**. Failures identified missing maturity/digest semantics,
  live acceptance, the explicit uncertified walkthrough, and draft start flags.
  The real CLI help assertion already passed.
- First GREEN: the same command produced **5 passed in 0.08s**.
- Relevant guide/CLI gate:
  `python -m pytest -q tests/test_course_authoring_docs.py tests/test_cli.py -k
  'course_authoring_docs or start_blocks_draft or start_include_drafts'`
  produced **7 passed, 87 deselected in 0.12s**.
- Direct CLI contract:
  `learnlab start --help` exited 0 and displayed `--include-drafts`.
- Full offline suite:
  `python -m pytest -q -m 'not live'` produced
  **485 passed, 1 deselected in 30.44s**.
- Ruff initially reported only import ordering in the new test. `ruff check
  --fix` corrected it and `ruff format` reported the file unchanged.

## Self-review and remaining limits

Checked the guide wording against `course_certification.py`, `curriculum.py`,
the actual Typer start command, and the existing draft-gate CLI regressions.
The docs do not claim provider-aware validation probes installed guest
software, and the provider lifecycle test is separated from course acceptance.
The record example uses all and only the implemented fields. Start examples for
unproven courses include the real CLI flag; resume remains state-dependent and
does not accept that flag.

These documentation tests protect commands, maturity terms, checklist shape,
and the live parser flag. They cannot establish runtime guest compatibility or
successful infrastructure cleanup. No provider, SSH, guest, or live command
was run. Every shipped course remains draft until its final digest completes
the separately approved live acceptance protocol. Registry date and revision
facts must be recorded only after such a run; they were intentionally not
invented here.
