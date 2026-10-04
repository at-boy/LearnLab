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
