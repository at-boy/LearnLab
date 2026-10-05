# Final integrated review — Debian 13 template course

Reviewed 2026-10-05 at `7a83a46b009ba32ea26753fa393819f727f59a86`.
Scope: approved design/plan, offline report, and supplied integrated diff
`7ae9939..c556dfa`, with focused provenance and shared-test inspection.

## Verdicts

- **Specification: needs changes** — the two-clone remote sudo acceptance
  instruction below can check the wrong machine.
- **Quality: needs changes** — one P2 finding; no additional blocking findings
  in the integrated scope. Resolve it in both curriculum and guide before
  closing the offline review gate.
- **Live certification: not performed, pending, course remains draft.** Offline
  tests and this review do not certify guest installation, sealing, clone
  identity, mutation permissions or cleanup.

## Actionable finding

### P2 — Keep the sudo acceptance check inside SSH

`src/learnlab/collections/proxmox/courses/debian13-template/lessons/05-test-two-clones/lesson.yaml:62–67`
(the critical command/continuation is lines 66–67), also
`docs/Debian13-Template-Guide.md:382–383`.

The command ends with `id -un`, so SSH runs that remote command and exits.
There is no remaining authenticated session in which to run the prescribed
next `sudo -n true`. A learner following the displayed sequence runs sudo on
the controller: controller passwordless sudo can falsely pass acceptance when
clone sudo is broken, while controller sudo restrictions can cause a false
failure. The guide repeats this by referring to section 3's same one-shot SSH
command. Show an explicit remote sudo command using the same strict SSH
options, or explicitly open an interactive session without `id -un` before
running guest checks. Apply consistently to both clones and the reboot recheck.
A focused local command-structure check is sufficient for this editorial fix;
no live access is needed.

## Integrated evidence checked

- Seven ordered packaged lessons use NONE scope, empty provider/guest
  dependencies and only knowledge/manual validations. Actual CLI and installed
  wheel tests exercise saved progress, self-attested records, forbidden
  settings/secret/provider/SSH access, unchanged registry and draft gating.
- Existing shared metadata coverage retains NONE/VM distinctions, all six
  pending-course checks and sibling bootstrap wheel coverage. Installed smoke
  uses the installed package path and a temporary working directory.
- Recomputed course digest:
  `8c815d9f0c3df55d0089f2a34c69d18c5cc89c467ed61fc99f14899dda2ce1af`.
  It matches the offline report. No source/test differences exist from course
  revision `51a6525` through reviewed HEAD; the report's reuse of current-content
  results is justified.
- Recomputed effective Debian downstream capability union matches the 15
  declared capabilities. No original six course contents or registry changed;
  current registry is `certifications: []`, and catalog maturity is draft.
- Accepted recorded current-content evidence: 666 non-live tests passed, one
  live test deselected; packaging 2 passed; focused Debian/CLI 8 passed; Ruff,
  mypy (17 files), catalog and whitespace checks passed. Reviewed Task 4's
  report for provenance; did not redundantly rerun the full suite or wheel.
- Guide/course agree on ownership inspection, explicit disk/sealing/conversion
  and clone-deletion decisions, recoverable source, service/key dependency,
  D-Bus identity, two-clone/reboot checks, private evidence and read-only profile
  handoff. Remaining target-version/runtime uncertainty is explicitly pending.
- Included provider-bootstrap TLS correction is compatible with the Debian
  optional handoff: a fresh lifecycle shell restores authenticated trust and
  retains it through reconciliation. Its historical evidence is distinguished
  from its updated digest. No new interaction finding.

## Closure and retained boundary

After the P2 correction, recompute the changed course digest, update the offline
report's revision/digest and covering verification, then obtain focused review
of the correction. Reconcile final-review-pending prose and Task 5 completion
checkboxes only after that gate passes. All exact-digest live checkpoints remain
pending, with the registry untouched. No infrastructure operation, implementation
edit, commit, merge or push was performed by this reviewer.

## Focused final disposition — 2026-10-05

Reviewed only `review-7a83a46..026fb27.diff` and `final-fix-report.md`, covering
course correction `7d696d4` and evidence update `026fb27`.

**P2 resolved. Specification: PASS for offline implementation. Quality: PASS.**
No remaining actionable findings in the reviewed change. Both lesson and guide
now run `sudo -n true` as an explicit remote SSH command with the same strict
per-clone trust and key options. They require both identity and sudo commands
to succeed independently for each clone and to be repeated after reboot.

Evidence provenance is correctly updated to digest
`b8b37477effe6444331d9a9e3c6a5398ec800eb3be7e05927b08ca2f8423c995` at
course revision `7d696d4`. The prior 666-pass suite and wheel results are
explicitly historical for `51a6525`, not attributed to changed course bytes.
Recorded covering checks are six Debian course tests, two Debian CLI tests,
course/catalog validation and whitespace checks; these are proportionate to
this instruction-only correction. This reviewer inspected the correction and
evidence without rerunning tests or opening any remote session.

This disposition supersedes the earlier needs-changes verdict and closes the
final offline review gate. The parent may now reconcile review-pending status
prose and completed offline Task 5 checkboxes. Exact-digest live acceptance
remains pending, the course remains draft, and the registry stays untouched.
No live certification, merge or push is implied.
