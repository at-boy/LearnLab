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

## Review round 1 correction

- A separately verified regular `/var/lib/dbus/machine-id` is now replaced with a verified symlink to `/etc/machine-id` during sealing, after checking file type, parent and mount. Clone acceptance requires a nonempty machine ID, byte equality through the link, and a matching live system-bus `GetMachineId` result before and after each reboot. The [D-Bus specification](https://dbus.freedesktop.org/doc/dbus-specification.html) expects both paths to agree; [dbus-uuidgen(1)](https://dbus.freedesktop.org/doc/dbus-uuidgen.1.html) does not repair an existing invalid file.
- Before disabling ssh.socket, the lesson now requires a verified ssh.service boot path. It inspects masked/disabled states, explicitly enables a startable service when needed, and stops on unresolved activation. Each clone must show ssh.service enabled and active with the key-generation dependency. Debian [systemctl(1)](https://manpages.debian.org/trixie/systemd/systemctl.1.en.html) distinguishes enabling a boot trigger from starting a unit.
- After these prose corrections, focused course tests passed **5/5**, worktree catalog validation passed with no findings, and `git diff --check` passed. The full suite was not rerun for this review correction; the earlier 664-pass result above predates these edits. No guest or Proxmox operation was performed.
