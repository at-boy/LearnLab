# Task 3 implementation report

Status: implemented; offline verified; no live certification.

Copied the Debian and NixOS nginx source families to canonical packaged curriculum, preserving originals. Added OS/tool capabilities, Debian 13 naming, fresh disposable guest prerequisites and cumulative/resume guidance. Corrected the NixOS response under learnlab.local and gave the later content host a distinct name. Made symlink enablement convergent, removed redundant manual attestations, bounded curl and privileged operations, and replaced source-grep evidence with runtime responses, parsed configuration and listener ownership checks. Proxy verification compares a fresh diagnostic token and forwarded header against the direct upstream. Logging uses a fresh token and saved byte offset; invalid syntax is exercised in an isolated temporary configuration. NixOS rollback instructions restore complete course source and verify all cumulative endpoints. Corrected dry-build and generation wording, and tightened the proxy and restart explanations.

## Red / green evidence

Interpreter: `/home/at-boy/Projects/codex/LearnLab/.venv/bin/python`; commands run in the pending-course-certification worktree.

- `python -m pytest tests/test_shipped_nginx_courses.py -q`: initial RED, 7 failures demonstrating missing capabilities, invalid NixOS option placement, unbounded probes, and missing fresh proxy/log evidence.
- Same focused command after correction: GREEN, 7 passed.
- Added negative restart-answer regression: RED, 1 failed / 7 passed because `I know it persists` matched `no`.
- Same focused command after anchored answer correction: GREEN, 8 passed; final formatted curriculum rerun also 8 passed.
- `PYTHONPATH=src python -c 'from learnlab.cli import app; app()' validate nginx/nginx-basics`: passed with no findings.
- Same validation for `nginx-nixos/nginx-basics`: passed with no findings.
- `python -m pytest -m 'not live' -q`: first gate 462 passed, 1 deselected; final content gate 463 passed, 1 deselected in 30.01s.
- `python -m ruff check tests/test_shipped_nginx_courses.py`: all checks passed after formatting.
- Parsed all lesson remote commands and ran `bash -n -c` without executing them: 34 passed.
- Scoped diff whitespace check passed. Initial CLI attempt using `python -m learnlab` failed because there is no __main__; corrected to the actual CLI app above.

## Self-review and limits

Self-review fixed temporary-file cleanup, separated port-80 and port-8080 NixOS host names, and corrected current-profile versus booted-generation wording. Runtime checks test intended behavior but offline tests cannot establish guest compatibility or certify a live course. nginx -T proves the on-disk configuration parses, while listener/response probes supply separate running-state evidence; it is not a dump of configuration currently resident in worker memory. Log rotation during the offset probe requires retry. Timed-out package/rebuild operations require inspecting state before retrying. No provider calls, guest commands, live rollback, or live acceptance occurred. Registry records remain absent, so both courses retain draft maturity under the controller-approved default. Full live completion/resume/failure/cleanup remains required before certification.

Initial ordinary staging was denied by the filesystem because the linked worktree index is in the read-only Git administrative directory; elevated scoped staging/commit is requested using the existing commit authorization.

## Review round 1

Corrected Debian's executable check to `sudo -n timeout 10 /usr/sbin/nginx -v`, avoiding the non-root PATH's omission of /usr/sbin. Removed the relative previous-generation rollback exercise: recovery now uses only the isolated invalid nginx configuration and verifies cumulative endpoints without changing system generations. Removed duplicate NixOS initial service-active verification, clarified that restart neither edits nor evaluates NixOS source, and aligned the generation failure message with nix-env.

Regression command `python -m pytest tests/test_shipped_nginx_courses.py -q`: RED 2 failed / 8 passed for the PATH and relative-rollback defects; GREEN 10 passed after corrections. Both actual CLI validate commands again passed with no findings. Ruff check passed; all 33 current remote commands passed bash -n without execution; git diff --check passed. No live operations occurred. This supersedes the earlier report's whole-system rollback exercise description; whole-system generation recovery remains outside this isolated exercise and requires a separately planned explicit target.
