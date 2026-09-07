# Course Discovery and Continuation Design

**Status:** Proposed for review

## Purpose

Make plain `learnlab` a useful interactive home screen while preserving
explicit, scriptable commands for listing, starting, resuming, and inspecting
courses.

## Commands

- `learnlab` opens the home screen only when stdin and stdout are interactive.
- `learnlab courses` lists available courses and local status without loading a
  provider or secret.
- `learnlab lessons COLLECTION/COURSE` lists ordered lessons and completion.
- `learnlab continue` resumes the most recently active incomplete course.
- `learnlab progress` shows all known local course progress.
- Existing `start`, `resume`, `progress complete`, `reset`, `destroy`, and
  `provider test` commands remain compatible.

In non-interactive use, plain `learnlab` prints concise help and exits zero. All
listing commands support deterministic plain output; `--format json` provides a
versioned machine-readable form.

## Home Screen

The home screen shows, in order:

1. the most recently active incomplete course and its next lesson;
2. other started courses;
3. available ready courses;
4. draft courses only when explicitly requested;
5. actions for continue, browse, progress, validation, provider health, or exit.

Selecting a course delegates to the same session entry point used by explicit
commands. The home screen owns presentation and selection only; it must not
duplicate lifecycle logic.

## Recency and Progress

StateStore exposes a read-only course-progress query returning collection,
course, per-status counts, next lesson, active environment presence, provider
profile when already recorded, and last activity timestamp. Recency is based on
persisted session/progress/environment timestamps, with stable course-path
ordering as a tie-breaker.

`continue` fails clearly when there is no incomplete started course. Completed
courses remain visible but are never selected as the default continuation.

## Provider Selection

Browsing and progress are entirely offline. Continuing reuses the profile
recorded with an existing environment when safe; otherwise it follows the
current default/explicit profile resolution and ownership checks. No listing
operation resolves the token secret.

## Error Handling

- Catalog entries that fail to load appear as validation errors rather than
  disappearing.
- State for a removed course is shown as unavailable historical progress.
- Non-TTY selection never prompts.
- Ctrl-C or EOF at the home screen exits without changing state.
- Session interruption retains the existing exit-130 and recovery behavior.

## Testing

- Catalog discovery and state aggregation receive focused unit tests.
- CLI tests cover empty, started, completed, removed, and malformed courses.
- Tests prove list/progress/home rendering does not load settings or secrets.
- Interactive tests cover selection and cancellation through injected prompts.
- JSON snapshots exclude secret and environment-specific fields not required by
  the contract.
- Existing explicit-command tests remain unchanged and passing.

## Out of Scope

- Full-screen terminal UI frameworks.
- Fuzzy search, paging, remote curriculum registries, and synchronization.
- Changing course/lesson ordering semantics.

## Success Criteria

A returning learner can type `learnlab`, immediately see where they stopped,
and continue without remembering a path, while automation retains stable
explicit commands and offline discovery never asks for a Proxmox secret.
