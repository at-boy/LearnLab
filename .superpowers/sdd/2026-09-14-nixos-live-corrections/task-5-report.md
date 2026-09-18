# Task 5 report — strict Proxmox TLS trust recovery

## Status

Complete. The provider-bootstrap course, NixOS template handoff, standalone
guide, and README now teach the Python 3.13 strict-verification failure mode and
the bounded, out-of-band-authenticated server-leaf fallback without changing
the provider schema, provider code, NONE-scope course boundaries, or
`token_secret_env` semantics.

## Files changed

- `.superpowers/sdd/2026-09-14-nixos-live-corrections/progress.md`
- `.superpowers/sdd/2026-09-14-nixos-live-corrections/task-5-report.md`
- `README.md`
- `docs/NixOS-Template-Guide.md`
- `docs/course-validation/2026-09-10-nixos-template.md`
- `docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md`
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/04-add-named-profile/lesson.yaml`
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/05-run-get-only-health/lesson.yaml`
- `tests/test_nixos_template_course.py`
- `tests/test_provider_bootstrap_course.py`

The two course-validation reports changed only because both exact course
digests changed with the intentional curriculum bytes. Their draft and
live-acceptance-pending status remains unchanged.

## RED evidence

Command:

```text
.venv/bin/pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py -k 'strict_tls_recovery or provider_handoff_teaches_authenticated_rotation_sensitive_tls_recovery'
```

Result:

```text
3 failed, 123 deselected in 0.24s
```

All three focused cases failed on the first missing required fragment,
`Python 3.13`, in the provider profile surface, NixOS course handoff, and NixOS
guide. The failures were caused by missing learner guidance, not syntax, fixture,
network, or live-environment errors. After the prose was added, an intermediate
focused run still failed because one assertion treated ordinary line wrapping
as semantic text; the assertion was corrected to normalize whitespace while
retaining every security-contract check.

## GREEN evidence

```text
.venv/bin/pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py -k 'strict_tls_recovery or provider_handoff_teaches_authenticated_rotation_sensitive_tls_recovery'
3 passed, 123 deselected in 0.20s

.venv/bin/pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py
126 passed in 6.20s

.venv/bin/python -m pytest -m 'not live'
655 passed, 1 deselected in 39.98s

.venv/bin/learnlab validate proxmox/provider-bootstrap
Validation passed with no findings.

.venv/bin/learnlab validate proxmox/nixos-template
Validation passed with no findings.

.venv/bin/ruff check tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py
All checks passed!

git diff --check
exit 0; no output
```

The affected-suite run first exposed the provider-bootstrap offline report's
digest-bound regression. Investigation confirmed that the intentional lesson
bytes changed `course_digest()`. Both exact-digest reports were refreshed, and
the complete affected suite then passed.

An initial optional full-suite invocation through the `pytest` console script
failed during collection because that entrypoint did not put the current
worktree on `sys.path`, while a provider test imports the namespace package
`tests`. The repository-standard `.venv/bin/python -m pytest` entrypoint
collected all 656 items from this worktree and produced the full green result
above. This was an invocation-path artifact, not a product or test failure.

## Commit SHA

The report is included in the task commit, so it cannot contain that commit's
own SHA without changing the SHA. The authoritative task commit SHA is returned
to the controller immediately after commit creation. Exact subject:
`docs: teach strict Proxmox TLS trust`.

## Self-review

- The guidance keeps `tls_verify = true` and does not present disabling TLS as
  this course's remediation.
- Python 3.13 strict verification is distinguished from curl acceptance.
- The preferred repair is a correctly issued controller-trusted certificate
  with an exact endpoint SAN.
- The leaf fallback requires separate trusted-path authentication plus expected
  issuer/chain, exact SAN, validity-window, and SHA-256 fingerprint checks.
- An unchecked `openssl s_client` capture from the same untrusted connection is
  explicitly rejected as authentication.
- The public leaf stays in an owner-only controller file outside repository,
  TOML, progress/evidence, and secret stores.
- `SSL_CERT_FILE` is process-scoped, not a `ProxmoxProfile` field and not the
  token secret; `token_secret_env` still names only the token-secret variable.
- Cleanup and rotation-sensitive stop/re-authenticate/replace behavior is
  present in both operator flows.
- Added examples use only synthetic metavariables. A diff-only scan found no
  new live address, hostname, certificate, identity, VMID, token, or local
  absolute path.
- NixOS course and guide wording is aligned, provider-bootstrap lessons divide
  profile trust from check-time process setup, and README matches both.
- No source provider implementation, configuration schema, environment scope,
  provider capability, guest capability, or certification registry changed.

## Concerns

No implementation concern. The leaf-pin fallback is intentionally
rotation-sensitive and remains operational guidance pending any separately
authorized live acceptance; offline tests do not establish live TLS behavior.

No live or network operations, user-configuration access, certification update,
merge, or push occurred.
