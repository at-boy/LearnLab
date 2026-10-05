# Task 1 — Debian 13 template bootstrap entry

## Result

Added a draft, one-lesson `proxmox/debian13-template` course with effective `none` environment scope. The first lesson teaches controller/node/guest roles, an owner-only local worksheet, no-profile startup, the limits of saved manual progress, and inspection before resuming or any destructive work. Existing NixOS/provider curricula and the six pending courses were not changed by this task. The shared shipped-metadata test already handled NONE-scoped courses, so it needed no edit.

## TDD record

- RED: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_debian13_template_course.py tests/test_cli.py::test_debian13_template_start_and_resume_need_no_provider_configuration -q` → 3 expected failures: missing course manifest prevented catalog load, validation, and CLI start. No collection/import error.
- GREEN focused: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_debian13_template_course.py tests/test_shipped_course_metadata.py tests/test_cli.py::test_debian13_template_start_and_resume_need_no_provider_configuration -q` → 14 passed.
- Full non-live suite, first run: 660 passed, 1 failed, 1 deselected. Failure: `tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending`, because the concurrently edited provider-bootstrap course digest did not yet match its report.
- Full non-live suite, second run: 660 passed, 1 failed, 1 deselected. The digest matched, but the same test required the historical `Current-digest reviewed content revision: c952e759...` header text, which the concurrent report edit had removed. This is outside Task 1 files and was reported to the controller.
- `PYTHONPATH=src .venv/bin/python -m ruff check --no-cache tests/test_debian13_template_course.py tests/test_cli.py` → passed. `git diff --check` → passed.

## Review and boundary

The CLI test exercises the packaged course through actual start, exact learner answer, saved progress, and resume. Tripwires on settings, secret resolution, and provider construction stayed untouched. Course checks are text evidence and manual confirmation only. No provider, SSH, VM, disk, or live resource operation was performed. This one-lesson draft is an entry point for later lessons, not an accepted Debian template procedure or live certification.

The `.superpowers/` report directory is ignored by Git. The report remains in the assigned worktree and is not staged.
