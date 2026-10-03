# Debian primary-source check — 2026-10-04

Read-only documentation retrieval for offline authoring, not live acceptance.

- Debian 13 amd64 installation guide: https://www.debian.org/releases/trixie/amd64/ — retrieved successfully, build 20250803+deb13u1. Use fixed trixie/13 target, record exact ISO at live acceptance.
- machine-id manual: https://manpages.debian.org/trixie/systemd/machine-id.5.en.html — retrieved successfully. Inspect actual D-Bus fallback and empty-file first-boot semantics during sealing review.
- ssh-keygen manual: https://manpages.debian.org/trixie/openssh-client/ssh-keygen.1.en.html — retrieved successfully. Missing-key generation uses -A; preserve existing host keys.
- Proxmox qm reference: https://pve.proxmox.com/pve-docs/qm.1.html — web retrieval returned Internal Error. No claim of target-version verification. Installed-version help remains a live acceptance prerequisite.

These references support curriculum authoring only. No target guest, disk, service, firmware, clone, identity or provider was exercised.
