# Task 1 Report: Course Maturity and Certification Model

## Implemented

- Added `CourseMaturity` with `draft`, `offline-validated`, and
  `live-validated` states.
- Added a deterministic SHA-256 course digest over sorted relative file paths
  and exact file bytes. The course tree's absolute location is excluded.
- Added a strict YAML `CertificationRegistry` that validates the exact record
  schema: course path, digest, status, ISO validation date, LearnLab revision,
  guest capabilities, and note.
- Added fail-closed validation for unknown fields, malformed values, duplicate
  course records, and strings containing URLs, IP addresses, VMID labels, or
  token/secret patterns.
- Attached maturity to loaded courses and course summaries. Missing records or
  digest mismatches resolve to `draft`.
- Added the packaged empty certification manifest. The existing Proxmox course
  therefore remains draft because it has no exact live digest record.
- Added `learnlab start --include-drafts`. A normal `start` blocks draft and
  offline-validated courses before state initialization or provider access;
  an explicit flag allows them. Existing `resume` behavior remains available
  for saved sessions.
- Updated synthetic CLI and integration fixtures to declare live maturity when
  their purpose is to exercise behavior after the gate. Tests using the real
  unrecorded Proxmox curriculum opt in with `--include-drafts`.

No live infrastructure operations were run.

## TDD Evidence

### RED

Command:

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/python -m pytest tests/test_course_certification.py -q
```

Relevant result before implementation:

```text
FFFFFFFFF
9 failed in 0.05s
```

Each test failed at the unimplemented digest or registry method. This was the
expected failure because no digest calculation, registry parsing, or maturity
lookup existed. The first collection attempt also established that the new
public module did not yet exist; a minimal interface skeleton was then added so
the tests failed on the missing behavior rather than import collection.

The first combined curriculum/CLI run after the model implementation produced
three meaningful regressions: a stale-certificate test made its YAML invalid,
and two legacy-state tests attempted to start the real now-draft Proxmox
course. The stale test was changed to preserve valid YAML, and the unrelated
state tests now opt in explicitly.

The first full offline run reported:

```text
5 failed, 412 passed, 1 deselected in 28.61s
```

All five failures were synthetic interactive integration courses relying on
the old implicit-ready behavior. Their fixtures now declare live maturity
explicitly; the draft-default and opt-in behavior stays covered by dedicated
CLI tests.

### GREEN

Focused command:

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/python -m pytest tests/test_course_certification.py tests/test_curriculum.py tests/test_cli.py -q
```

Result:

```text
164 passed in 0.96s
```

Integration regression command:

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/python -m pytest tests/test_interactive_course_integration.py -q
```

Result:

```text
5 passed in 0.18s
```

Final full offline command:

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/python -m pytest -m 'not live' -q
```

Result:

```text
417 passed, 1 deselected in 26.60s
```

## Additional Verification

```text
/home/at-boy/Projects/codex/LearnLab/.venv/bin/ruff check src tests
All checks passed!

/home/at-boy/Projects/codex/LearnLab/.venv/bin/mypy src
Success: no issues found in 17 source files

git diff --check
(no output; exit 0)
```

An `importlib.resources.files("learnlab")` smoke check loaded the packaged
`certifications.yaml` through the `Traversable` interface and reported zero
records plus `draft` for `proxmox/proxmox-admin`.

## Files Changed

- `src/learnlab/course_certification.py`
- `src/learnlab/collections/certifications.yaml`
- `src/learnlab/curriculum.py`
- `src/learnlab/cli.py`
- `tests/test_course_certification.py`
- `tests/test_curriculum.py`
- `tests/test_cli.py`
- `tests/test_interactive_course_integration.py`
- `.superpowers/sdd/2026-09-08-pending-course-review-certification/task-1-report.md`

## Self-Review

- Confirmed stale or missing digests cannot produce ready status.
- Confirmed the start gate precedes state database initialization and provider
  configuration access.
- Confirmed every certification value has a constrained type or format and
  infrastructure/secret-like strings are rejected.
- Confirmed draft records remain valid because the design calls for all three
  maturity states to be represented in the repository manifest.
- Confirmed the packaged manifest is included by the existing packaging tests
  in the full suite.
- Reviewed the complete diff and removed formatter-only changes outside the
  task.

## Concerns

None. The empty manifest intentionally leaves every currently shipped course
unready until an exact digest is certified by later tasks.
