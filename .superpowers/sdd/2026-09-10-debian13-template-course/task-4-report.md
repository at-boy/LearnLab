# Task 4 report — Debian 13 profile handoff and packaged course

## Outcome

- Added the seventh, NONE-scope `configure-provider` lesson and final manifest
  order. It teaches a new named profile using the current `ProxmoxProfile`
  schema, the exact effective capability union of the three matching Debian
  downstream courses, read-only learner-run health/validation checks, and
  explicit cleanup of only two learner-owned clones after full identity and
  separate destruction confirmation.
- Completed the standalone Debian 13 guide, linked it in README, and documented
  version assumptions, primary sources, expected results, troubleshooting and
  the untested live boundary. No profile, secret, provider, SSH, guest or
  Proxmox resource was accessed by the work.
- Extended existing CLI and single installed-wheel smoke paths to exercise
  Debian draft gating, NONE-scope start/save/resume and self-attested handoff.
  Existing six pending-course and sibling bootstrap checks were preserved.
  The certification registry was not edited.

## TDD and verification

- RED: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_debian13_template_course.py -q` reported 2 expected failures, for absent seventh lesson and handoff, with 4 passes.
- GREEN: the same focused file reported 6 passes after implementation.
- Focused Debian course/CLI selection: 8 passed, 96 deselected.
- `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_packaging.py -q`: 2 passed. The existing wheel test built and installed one wheel within that invocation and exercised all preserved smoke cases plus Debian.
- `PYTHONPATH=src .venv/bin/learnlab validate proxmox/debian13-template --format json`: `ok: true`, no findings. A preliminary `python -m learnlab` invocation was invalid because the package has no `__main__`; the installed entry point above is the correct command.
- `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider -m 'not live' -q`: 666 passed, 1 live test deselected. This full-suite run also re-exercised the packaging wheel test.
- `PYTHONPATH=src .venv/bin/ruff check --no-cache tests/test_cli.py tests/test_debian13_template_course.py tests/test_packaging.py`: passed after formatting two long assertions. The embedded installed smoke script parses after that formatting change. `git diff --check`: passed.

## Editor review and remaining boundary

Reviewed the lesson and guide instructions against the design's cleanup and
certification boundaries: `learnlab destroy` is explicitly prohibited for
these untracked clones; a failed lookup alone cannot establish absence; each
clone requires full identity, shutdown and separate destruction confirmation;
template and source are retained. Profile health and downstream validation are
read-only compatibility checks, not mutation permission tests or certification.
TLS stays enabled; any `SSL_CERT_FILE` fallback requires independently
authenticated trust in each shell used for provider commands.

The Debian and systemd primary pages were reachable during this pass. The
Proxmox `qm` reference endpoint did not return usable content, so its exact
target-version behavior and all guest/resource procedures remain for a
separately authorized live acceptance run. Course maturity remains draft.
