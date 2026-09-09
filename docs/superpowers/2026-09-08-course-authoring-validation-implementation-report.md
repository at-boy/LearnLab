# Course Authoring and Validation Implementation Report

## Status

Implemented and verified by the complete offline gate. No live Proxmox test or
course certification was run or claimed.

## Delivered behavior

- `src/learnlab/collections/` is the single maintained and packaged curriculum
  tree; discovery is deterministic and strict.
- `learnlab validate [COURSE]` aggregates offline schema, layout, semantic, and
  authoring-lint findings without reading configuration, state, secrets, SSH,
  or providers. Human and exact schema-v1 JSON output support exit codes 0, 1,
  and 2.
- `--provider PROFILE` runs only after offline validation, resolves only that
  named profile, compares declared template and effective guest capabilities,
  and calls the read-only health boundary. Operational failures are redacted
  and exit 3.
- VM policy supports optional provider-neutral guest capabilities, including
  numeric dot segments such as `os.debian.13`. Lesson policies replace rather
  than merge course policy. Legacy `requirements` is temporarily mapped with a
  warning and cannot be mixed with `guest_capabilities`.
- The wheel smoke installs the artifact and exercises installed curriculum,
  `validate --help`, and schema-v1 JSON validation.

## Preserved rulings

- Missing `os.*` capability and unknown provider-check names remain warnings,
  matching the design's authoring-lint scope.
- Catalog discovery ignores non-directory entries but validates every
  discovered collection and course directory.
- Only tracked reviewed curriculum was migrated. Six untracked draft course
  directories in the main checkout remain outside this worktree for the
  separate certification plan and were not packaged.
- Capability declarations and provider health are compatibility and readiness
  evidence, not proof of installed guest contents, live lesson behavior, or
  certification.

## Verification

On 2026-09-09:

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/python -m pytest -m 'not live' -q
396 passed, 1 deselected in 26.42s

/home/at-boy/Projects/codex/LearnLab/.venv/bin/ruff check .
All checks passed!

/home/at-boy/Projects/codex/LearnLab/.venv/bin/mypy src
Success: no issues found in 16 source files
```

`git diff --check` produced no output after all documentation and report edits.
Git staging, commit, merge, and push remain with the controller.
