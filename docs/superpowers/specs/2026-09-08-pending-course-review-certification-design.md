# Pending Course Review and Certification Design

**Status:** Proposed for review

## Purpose

Review, correct, package, and certify the six pending nginx, nftables, and
systemd courses without representing untested content as production-ready.

## Scope

The work covers these course paths:

- `nginx/nginx-basics`
- `nginx-nixos/nginx-basics`
- `nftables-debian13/nftables-basics`
- `nftables-nixos/nftables-basics`
- `systemd-debian/service-authoring`
- `systemd-nixos/service-authoring`

It also revises `docs/LearnLab-Course-Authoring-Guide.md` to match the finalized
authoring contract from the course-validation workstream.

## Review Model

Each course advances through three explicit states recorded in a repository
manifest: `draft`, `offline-validated`, and `live-validated`. Installed LearnLab
may list draft courses but labels them clearly and requires an explicit
`--include-drafts` selection to start them. Only live-validated courses are
presented as ready by default.

Certification records non-secret facts only: course path, curriculum digest,
guest capability set, validation date, LearnLab version/commit, and a short
human test note. It contains no provider profile, endpoint, VMID, node, IP,
token, or personal infrastructure name.

## Required Corrections

Before live testing:

- Place NixOS nginx locations under a named virtual host.
- Replace the nftables localhost `prerouting` tests with a topology that
  actually traverses the taught hook, or narrow the lesson to a locally
  testable rule with accurate packet-flow explanation.
- Trigger nftables drop logging through a non-loopback path that is not already
  accepted.
- Declare Debian/NixOS and required-tool guest capabilities for every course.
- Tighten overly broad text-evidence regular expressions.
- Confirm every command is idempotent, non-interactive, bounded, and safe to
  retry after resume.
- Make prerequisites and cumulative state explicit at the beginning of each
  course.

The nftables NAT lessons may be marked draft and deferred to the multi-machine
workstream if honest automated validation requires a second machine. They must
not be weakened into manual confirmation merely to obtain a green result.

## Live Acceptance Protocol

Live validation is opt-in and destructive because it provisions course
environments. It uses scratch profiles selected by the operator and never runs
as part of the ordinary test suite.

For every course, the operator must:

1. Validate offline and against the intended read-only profile.
2. Start from a fresh compatible template.
3. Complete every lesson and verification in order.
4. Intentionally fail at least one check and assess its remediation message.
5. Save and exit mid-lesson, then resume at the first incomplete check.
6. Confirm expected cumulative course state.
7. Destroy the scratch environment through LearnLab and verify absence.
8. Record a certification only after cleanup succeeds or uncertain state has
   been reconciled.

## Guide Revision

The guide must describe the canonical curriculum path, `learnlab validate`,
guest capabilities, draft/certification semantics, versioning consequences,
and the difference between structural, provider-aware, and live validation. Its
walkthrough must either be exercised on a compatible image or clearly labeled
as an illustrative draft.

## Safety

- Never run live acceptance without explicit confirmation and a scratch
  profile.
- Preserve uncertain infrastructure state and recovery guidance on interruption.
- Do not broaden Proxmox permissions to make a course pass without a separate
  least-privilege review.
- Do not commit personal infrastructure values or test evidence containing
  them.
- A failed cleanup blocks certification but does not justify deleting by VMID
  alone.

## Testing

- Data-driven tests load every shipped course and assert declared status and
  capability metadata.
- Focused regression tests cover each corrected curriculum defect.
- Documentation tests ensure commands and paths match the CLI.
- Each course receives a completed live checklist outside the default suite.
- Packaging, wheel installation, offline tests, Ruff, mypy, and diff checks
  must pass before any course is marked ready.

## Success Criteria

Every pending course is either demonstrably live-validated on a compatible
fresh image or remains visibly draft with a precise blocker. The authoring guide
describes the actual implemented workflow, and no untested course is presented
as production-ready.
