# Task 2 independent review

Verdict for `3d4b14d..3e5da80`: **spec PASS; course-quality CHANGES REQUESTED**.

The three lessons are ordered in the manifest, retain effective `none` scope and draft status, use only learner-run actions and manual confirmations for infrastructure state, and separate the three exact-token knowledge checks from those confirmations. The tests exercise accepted and rejected answers through `TextEvidenceValidator`. Installation covers the official image, VM settings, network checks, disk identification and explicit write confirmation, disk-only boot, release checks, agent and package checks. The guide maps the downstream capability union. I found no instruction that automates a destructive guest operation or asks LearnLab to collect secrets.

## Findings

1. **P1 — Define the actual lab sudo rule and test representative commands.** `src/learnlab/collections/proxmox/courses/debian13-template/lessons/03-configure-lab-access/lesson.yaml:85-94` and `docs/Debian13-Template-Guide.md:127-132` tell a learner to grant a “minimal policy” but give no fragment content or command set. A rule permitting only `/usr/bin/true` would satisfy `sudo -n true` while the downstream apt, nftables, user-management and systemd exercises remain unusable. State the intended disposable-lab account rule explicitly, its scope and ownership/mode, and verify representative privileged commands or `sudo -n -l` against that rule. Keep the separate console recovery route.

2. **P2 — Make account lookup and key enrollment executable without the guide.** `src/learnlab/collections/proxmox/courses/debian13-template/lessons/03-configure-lab-access/lesson.yaml:50-64` says “`getent passwd` returning no entry” without an account argument; bare `getent passwd` enumerates the database and cannot establish whether the intended account exists. Specify `getent passwd <chosen-account>` and the local-account/NSS diagnosis, then give the learner the concrete way to inspect the guest host-key fingerprint and perform a fresh controller login using the separate known_hosts file with strict checking. The current guide repeats the same high-level direction at `docs/Debian13-Template-Guide.md:116-125`, so it does not fill this gap.

## Evidence and limits

I read the Task 2 brief and report, the supplied diff once, the linked Debian design's global, installation and lab-access requirements, the changed lessons, guide and tests. The implementation report records catalog validation, focused tests and 663 non-live tests passed with 1 deselected; I did not rerun them because the findings concern instructional completeness. No guest, Proxmox, provider, network, merge or push action was performed.

## Re-review of `3e5da80..0140b92`

**Finding 1 resolved.** The lesson and guide now give the exact lab-only `NOPASSWD: ALL` rule for the named account, root ownership and mode, `visudo` checks, an effective-rule listing, and read-only checks of representative privileged commands. This supports the downstream exercises and retains console recovery.

**Finding 2 resolved.** Lookup now names the intended account, distinguishes local-file and NSS failures, and the SSH sequence compares a console-observed host-key fingerprint with an isolated scanned key before strict login. The guide and lesson each contain the steps.

**New P2 finding — Allow a protected private key to be used in the login check.** `src/learnlab/collections/proxmox/courses/debian13-template/lessons/03-configure-lab-access/lesson.yaml` in `enroll-trusted-key`, and `docs/Debian13-Template-Guide.md` in “SSH trust,” recommend an existing or newly generated protected key but run `ssh` with `BatchMode=yes` without first loading that key into an agent. Batch mode disables interactive prompts, so a passphrase-protected key without an agent can fail even though SSH enrollment is correct. Instruct the learner to unlock the selected key in an agent first, or allow its local passphrase prompt while still rejecting a guest-account password and retaining strict host checking. The local `ssh_config(5)` documents BatchMode's prompt suppression.

**Updated verdict: spec PASS; course-quality CHANGES REQUESTED** for this narrowly introduced login usability issue. The correction report records focused tests 4 passed, catalog validation with no findings and a clean diff; I did not rerun tests or expand the review beyond these fixes.

## Final scoped re-review of `0140b92..f90c648`

**Passphrase finding resolved.** The lesson and guide remove `BatchMode=yes`, explicitly disable guest password and keyboard-interactive authentication, prefer public-key authentication, and allow a hidden local prompt for the private-key passphrase. Isolated known_hosts and strict host-key checking remain. I found no regression in this small change.

**Final Task 2 verdict: spec PASS; course-quality PASS — no open actionable findings.** The implementer reports focused tests 4 passed, catalog validation with no findings, and a network-free `ssh -G -F /dev/null` option check. I reviewed the diff and report only; I did not rerun tests or make a network connection.
