# Template Bootstrap Course Tasks

Requested 2026-09-10; planning completed 2026-09-11. These are repository task
handoffs for later sessions, not active background jobs. No course implementation
or live infrastructure work has started.

The pending-course implementation was merged and pushed at `287d350`. Its six
courses remain draft pending separate live acceptance. The preserved branch is
`feature/pending-course-certification`.

| Task | Course | Status | Spec | Implementation plan |
|---|---|---|---|---|
| Build the NixOS template course | `proxmox/nixos-template` | Planned; ready for a later session | [Design](../specs/2026-09-10-nixos-template-course-design.md) | [Plan](../plans/2026-09-10-nixos-template-course.md) |
| Build the Debian 13 template course | `proxmox/debian13-template` | Planned; ready for a later session | [Design](../specs/2026-09-10-debian13-template-course-design.md) | [Plan](../plans/2026-09-10-debian13-template-course.md) |

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

> Implement `docs/superpowers/plans/2026-09-10-nixos-template-course.md` and its
> linked spec using sub-agents, TDD and review gates. Use an isolated worktree
> from current main. Finish all authorized offline work, keep the course draft
> without live evidence, and stop before live resource operations for explicit
> approval. Do not merge or push implicitly.

### Debian 13

> Implement `docs/superpowers/plans/2026-09-10-debian13-template-course.md` and its
> linked spec using sub-agents, TDD and review gates. Use an isolated worktree
> from current main. Finish all authorized offline work, keep the course draft
> without live evidence, and stop before live resource operations for explicit
> approval. Do not merge or push implicitly.
