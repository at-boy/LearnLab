# SDD ledger — bounded design: NixOS live-discovered identity and boot corrections

Authority: `docs/superpowers/specs/2026-09-10-nixos-template-course-design.md`
Plan: `docs/superpowers/plans/2026-09-10-nixos-template-course.md`
Implementation base: `3bb629d697b530d2948265affd74ea2c6a5ceddf`
Workspace: `/home/at-boy/Projects/codex/LearnLab/.worktrees/template-bootstrap-course`

Approved design: require a stopped VM before post-install boot-order mutation; derive each clone's four-byte `/etc/hostid` from its freshly generated `/etc/machine-id` without a static `networking.hostId`; seal machine-id, hostid, and exact configured SSH host-key pairs; prove cross-clone distinctness and per-clone reboot stability.

Ruling: the first-boot hostid service is appropriate for this ext4 course template and runs after machine-id availability before multi-user completion. It fails closed on absent/malformed machine-id, writes a same-filesystem temporary four-byte file, then atomically installs `/etc/hostid`. It is not presented as a ZFS boot design. Cost if wrong: services needing hostid earlier than multi-user would require an earlier unit; the shipped course does not use ZFS or such a service.

Task 1: complete — commit `29d756d` (`3bb629d..29d756d`), independent spec and quality review clean. RED 14 failed/27 passed; focused 60 passed; related 189 passed; full non-live 625 passed, 1 deselected; validator, Ruff, mypy, changed-file formatting and whitespace clean. Nix evaluation/live behavior remains pending.
Task 2: pending — revised offline/live report after course bytes and live acceptance stabilize.

Task 3: complete — add a QGA sealing alternative for console-paste failure without
weakening console recovery or candidate-SSH trust boundaries. The QGA preflight
requires revalidated candidate identity/layout and effective `sshd -G -T` ports/
host-key paths; the deliberate request stops all SSH listeners/sessions/processes
(including `sshd-session`), validates exact files, seals them, syncs, requests
poweroff and requires positive Proxmox Stopped state. Failure, partial/uncertain
output or interruption requires reconciliation, never a blind rerun. No rebuild,
restart, reboot, conversion, force flag, glob or recursive deletion was added.
RED: focused QGA regression failed 2/2 because the sealing fallback was absent.
GREEN: 70 course tests passed; offline validation, Ruff and `git diff --check`
passed. Live QGA/guest/Proxmox behavior remains pending explicit authorization.
