# Task 3 — Debian sealing and two-clone acceptance

## Delivered

- Added `seal-and-convert` and `test-two-clones` to the course manifest, with complete manual inspect/confirm/execute/verify steps and separate non-secret concept checks.
- Added matching standalone guide sections. The procedure retains a recoverable source, refuses uncertain identity/snapshot state, orders missing SSH host-key generation before SSH, handles D-Bus and the active DHCP client by inspected type, powers off without reboot after sealing, and compares two full clones before and after individual reboots.
- Added catalog order/step checks and real `TextEvidenceValidator` positive/negative cases. No executable shell guard or lifecycle helper was introduced, so there is no guard to run with stubs. Prose safety and command applicability need editorial and live operator review.

## TDD and offline evidence

- RED: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/test_debian13_template_course.py -q` failed 3 tests for absent lessons (order, knowledge checks, step checkpoints); 2 existing tests passed.
- GREEN: same focused command passed 5 tests.
- Full offline gate: `PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider -m 'not live' -q` passed **664**, with **1 deselected**, in 40.63 seconds.
- `PYTHONPATH=src .venv/bin/learnlab validate proxmox/debian13-template`: passed with no findings.
- `git diff --check`: passed.

## Source review and limits

- Debian trixie [machine-id(5)](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html) confirms the D-Bus fallback and that an existing empty `/etc/machine-id` does not satisfy `ConditionFirstBoot=yes`.
- Debian trixie [ssh-keygen(1)](https://manpages.debian.org/trixie/openssh-client/ssh-keygen.1.en.html) confirms `-A` generates only missing default host keys. Debian [systemd.unit(5)](https://manpages.debian.org/trixie/systemd/systemd.unit.5.en.html) confirms `Requires=` must be combined with `After=` for ordered failure propagation; [systemd.service(5)](https://manpages.debian.org/trixie/systemd/systemd.service.5.en.html) documents `TimeoutStartSec=` for oneshot startup.
- The [Proxmox administration guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.pdf) was available for template/full-clone background. The `qm.1` page in the spec returned an internal error during this task. UI details and snapshot behavior must be confirmed against the learner's actual Proxmox version at live acceptance.
- No guest, provider, Proxmox or live infrastructure action was performed. The course remains draft. Missing-key boot ordering, D-Bus/DHCP behavior, full-clone identity distinction, SSH authentication and reboot stability remain live acceptance checks; offline passing does not certify them.
