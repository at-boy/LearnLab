# Task 2 report — Debian installer and lab access

Implemented the three ordered lessons `create-installer-vm`, `install-debian13`
and `configure-lab-access`, and started the standalone guide with complete
installation and access sections. The course remains draft and all four
lessons retain effective environment scope `none`.

## TDD and validation evidence

- RED: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_debian13_template_course.py -q` → 2 failed, 2 passed. The manifest contained only the introductory lesson, so the new catalog sequence and knowledge-check test failed for missing lessons/checks.
- GREEN: same focused command → 4 passed. The table-driven knowledge test executes the actual `TextEvidenceValidator` for accepted and rejected answers from each new lesson.
- `PYTHONPATH=src .venv/bin/learnlab validate proxmox/debian13-template` → validation passed with no findings.
- `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider -m 'not live' -q` → 663 passed, 1 deselected in 41.60s.
- `git diff --check` → no whitespace findings.

The first attempted `python -m learnlab validate` failed because this package
has no `__main__`; the supported `learnlab` entry point succeeded immediately
afterward. No guest, Proxmox or provider operation was run.

## Source and editorial review

Read the official Debian 13 amd64 installation guide, Debian 13 installer
page and Debian image verification procedure. The lessons pin trixie/amd64,
require authenticated checksums, distinguish the EFI variables disk from the
OS disk, and demand an explicit installer write summary before partitioning.
Access instructions retain console recovery until fresh trusted key login and
checked sudo succeed. The guide maps all 15 current downstream capabilities
to Debian commands/packages; the base guest is not preloaded with exercise
state. Reviewed the instructions for unconditional disk formatting, automatic
cleanup and secret evidence prompts; none were introduced.

## Remaining boundary

Instructional prose and Proxmox UI behavior still need live operator
acceptance against the target platform. No current guest, disk, agent, key,
service or template behavior is certified. The guide will gain sealing,
two-clone and provider sections in later tasks.

## Independent review round 1 correction

The reviewer requested concrete lab sudo and SSH/account procedures. The
access lesson and guide now specify the exact disposable guest sudoers rule,
root ownership and 0440 mode, `visudo` validation, an effective-rule listing,
and non-mutating checks for root identity, apt, nft and systemctl. They also
specify named-account `getent` lookup with local-file/NSS diagnosis, a guest
console host-key fingerprint, comparison with a separately captured controller
key, and strict SSH login through a new isolated known_hosts file. This is
instructional content only; no guest or network command was executed. Debian
trixie `sudoers(5)`, `ssh(1)` and `ssh-keygen(1)` manpages were consulted.

After the correction: focused course tests → 4 passed; packaged course CLI
validation → no findings; `git diff --check` → clean. The prior full non-live
suite remains the Task 2 baseline; this prose-only correction did not alter
runtime code, metadata or test behavior.

## Independent review round 2 correction

Removed `BatchMode=yes` from the SSH login example in the lesson and guide.
The command now disables guest password and keyboard-interactive methods and
prefers public-key authentication while allowing a hidden local prompt to
unlock a protected private key. Strict host-key checking and the isolated
known_hosts file remain in place. No private-key material is transferred.

After the correction: focused course tests → 4 passed; packaged course CLI
validation → no findings. A network-free `ssh -G` check with an empty client
config confirmed `passwordauthentication no`, `kbdinteractiveauthentication no`,
`preferredauthentications publickey`, strict host checking and the isolated
host-key paths. The host's system SSH config had a permissions error, so the
read-only option check used `-F /dev/null`; no SSH connection was attempted.
