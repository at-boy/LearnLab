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

## Fix round 1 — live-evidence provenance

### Findings addressed

1. Both course-validation reports now label their older revisions and checks as
   historical evidence. Their unchanged current digests and Task 5 offline
   results are explicitly bound to reviewed course-content revision
   `c952e759b34fd5592f5c0607eef8d5474567433a`.
2. The NixOS report now records, without identifiers, the separately authorized
   installation, sealing, template conversion, two-full-clone rebuild/reboot,
   and read-only provider health/compatibility observations that occurred before
   the TLS documentation commit/current digest. It states that this prior-digest
   evidence does not certify current course bytes and that current-digest course
   traversal/save-resume and acceptance-clone cleanup remain pending. The
   provider-bootstrap report scopes its prior read-only health/compatibility
   observation to the NixOS handoff, rejects it as full provider-bootstrap
   acceptance, and keeps the separately authorized scratch lifecycle incomplete.

Both reports retain draft status and describe Task 5 as offline-only.

### RED evidence

Command:

```text
.venv/bin/python -m pytest tests/test_nixos_template_course.py::test_offline_report_binds_current_digest_and_scopes_prior_live_evidence tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending tests/test_provider_bootstrap_course.py::test_offline_report_scopes_prior_health_to_incomplete_current_acceptance -q
```

Result before report edits:

```text
3 failed in 0.14s
```

The failures were the intended report-contract failures: neither report named
`c952e759...` as the current-digest reviewed content revision, and the required
prior-observation/current-digest boundary was absent. The digest assertions
already passed, proving that the defect was provenance text rather than stale
course bytes.

### GREEN evidence

```text
.venv/bin/python -m pytest tests/test_nixos_template_course.py::test_offline_report_binds_current_digest_and_scopes_prior_live_evidence tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending tests/test_provider_bootstrap_course.py::test_offline_report_scopes_prior_health_to_incomplete_current_acceptance -q
3 passed in 0.07s

.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py
128 passed in 5.86s

.venv/bin/python -m pytest -m 'not live'
657 passed, 1 deselected in 40.28s

.venv/bin/learnlab validate proxmox/nixos-template
Validation passed with no findings.

.venv/bin/learnlab validate proxmox/provider-bootstrap
Validation passed with no findings.

.venv/bin/ruff check tests/test_nixos_template_course.py tests/test_provider_bootstrap_course.py
All checks passed!

git diff --check
exit 0; no output
```

One initial post-edit Ruff run found only an overlong new test literal; wrapping
the literal without changing its value resolved the formatting failure.

### Unchanged digest evidence

Read-only recomputation produced:

```text
proxmox/nixos-template c1a124cf56f0ce19b8203926bde0d6e8305e71a175f823f90200318c3279dc82
proxmox/provider-bootstrap 92efd4934b2584f75e0acbc6260b8d66873f74a0da11f318e832632f2d72fda2
```

These values exactly match Task 5 and confirm that fix round 1 changed no course
manifest or lesson byte. The reports/tests/report artifacts therefore continue
to associate those course digests with reviewed content revision `c952e759...`.

### Commit SHA handling

This appended report is included in the fix commit and therefore cannot contain
that commit's own SHA. The authoritative SHA is returned to the controller after
commit creation. Exact subject: `docs: correct live evidence provenance`.

### Self-review and concerns

- Diff scope is limited to the two course-validation reports, their two test
  modules, and this append-only Task 5 report.
- No lesson, manifest, README, standalone guide, provider code/schema,
  certification registry, user configuration, or live state changed.
- The reports contain no live identifiers, secrets, fingerprints, certificate
  dates/content, token identities, VMIDs, or local absolute paths.
- Historical observations are not promoted to current-digest acceptance or
  certification; current-digest pending work remains explicit.

No implementation concern. No live or network operation, certification update,
merge, or push occurred during fix round 1.
