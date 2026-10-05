# Final reviewer P2 correction — Debian clone sudo check

Course and guide correction: `7d696d4` (2026-10-05). The one-shot strict SSH
`id -un` command exits before any subsequent local command. Lesson 05 and the
guide now show a second, explicit remote `sudo -n true` command with the same
per-clone known-hosts, public-key-only and identity-file options. Both commands
must succeed for A and B; after each reboot, the learner repeats the trusted
host-key comparison and both strict remote commands. No controller-side sudo
result is presented as clone acceptance.

Current course digest:
`b8b37477effe6444331d9a9e3c6a5398ec800eb3be7e05927b08ca2f8423c995`.
The earlier `8c815d9f0c3df55d0089f2a34c69d18c5cc89c467ed61fc99f14899dda2ce1af`
and full 666-pass / wheel results belong to previous course bytes at `51a6525`;
they are retained only as historical context in the acceptance report.

Focused current-content verification: Debian course tests 6 passed; Debian CLI
tests 2 passed (96 deselected); course validation `ok: true` with no findings;
catalog validation `ok: true` with only the three existing `proxmox-admin`
warnings; seven lessons load as `draft`; registry remains `certifications: []`;
`git diff --check` clean. The guide and lesson commands were compared locally.
No network SSH, provider, guest or Proxmox action occurred.

The P2 correction awaits focused independent re-review. Exact-digest live
acceptance and certification remain pending; no merge or push occurred.
