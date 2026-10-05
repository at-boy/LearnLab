# Template Bootstrap Course Tasks

Requested 2026-09-10; reconciled 2026-10-05 against code and completion reports.
NixOS and provider-bootstrap are implemented offline; current-content live
acceptance remains pending. See [roadmap status](../../roadmap/status.md).

The pending-course implementation was merged and pushed at `287d350`. Its six
courses remain draft pending separate live acceptance. The preserved branch is
`feature/pending-course-certification`.

| Task | Course | Status | Spec | Implementation plan |
|---|---|---|---|---|
| Build the NixOS template course | `proxmox/nixos-template` | Implemented; later corrections on preserved branch; live acceptance pending | [Design](../specs/2026-09-10-nixos-template-course-design.md) | [Plan](../plans/2026-09-10-nixos-template-course.md) |
| Build the Debian 13 template course | `proxmox/debian13-template` | Offline implementation and final review passed; draft, live acceptance pending | [Design](../specs/2026-09-10-debian13-template-course-design.md) | [Plan](../plans/2026-09-10-debian13-template-course.md) |

Both courses begin without an existing template/provider profile, use the
existing NONE-scope instructional session, and leave Proxmox/guest operations
with the learner. They finish with two-clone identity checks and a provider
profile. Runtime confirmations remain visibly self-attested. The NixOS course
adapts the corrected **Plan NixOS Learning Lab** guide; the Debian course uses
the same teaching style with Debian-specific installation and identity handling.

Implement either first. Both touch shared metadata/CLI/packaging tests and
README, so separate sessions must preserve each other's changes and integrate
sequentially. Neither requires an engine image-builder or the other course.

## Suggested new-session prompts

### NixOS

> Resume integration review and current-content acceptance from
> `docs/roadmap/status.md`. Do not reimplement the completed course. Preserve
> `feature/nixos-template-course` and its worktree. Request approval before
> merge/push or live resource operations; do not certify historical observations.

### Debian 13

> Implement `docs/superpowers/plans/2026-09-10-debian13-template-course.md` and its
> linked spec using sub-agents, TDD and review gates. Use an isolated worktree
> from current main. Finish all authorized offline work, keep the course draft
> without live evidence, and stop before live resource operations for explicit
> approval. Do not merge or push implicitly.
