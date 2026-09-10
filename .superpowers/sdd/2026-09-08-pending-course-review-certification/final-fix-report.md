# Final consolidated fix wave

Base: `51376da`. Scope: the two final-review findings only.

Certification errors now become `invalid-certification` findings with relative
source paths and a remedy covering registry metadata and readable course files.
Malformed registry YAML and injected binary digest-read failures are covered in
validation and human/JSON CLI output. Offline dependencies are forbidden in those
CLI tests. Unexpected RuntimeError still propagates; no broad exception catch was
introduced. Provider handling is unchanged.

Audited all 13 text matches in both nginx families. Eight broad expressions now
use focused prompts and anchored accepted responses. All 13 have accepted,
incorrect, negated, and unrelated response coverage. Objective probes are unchanged.
Both nginx digests were recomputed after the final curriculum edits and recorded
in docs/course-validation/2026-09-08-pending-courses.md.

## Red and green evidence

Commands ran in this worktree with tools from
`/home/at-boy/Projects/codex/LearnLab/.venv/bin/`.

- RED: `pytest -q tests/test_course_validation.py tests/test_cli.py tests/test_shipped_nginx_courses.py`
  yielded **14 failed, 114 passed in 1.77s**. Failures reproduced certification
  exceptions escaping output and the eight broad nginx response matches.
- GREEN, same command after fixes: **128 passed in 1.59s**.
- Expanded audit and packaging: `PYTHONPATH=src python -m pytest -q tests/test_packaging.py tests/test_course_validation.py tests/test_cli.py tests/test_shipped_nginx_courses.py`
  yielded **135 passed in 3.29s**, including actual wheel build/install coverage.
- Final full offline gate: `PYTHONPATH=src python -m pytest -q -m 'not live'`
  yielded **513 passed, 1 deselected in 31.88s**.
- `ruff check .`: **All checks passed!**
- `mypy src`: **Success: no issues found in 17 source files**.
- `PYTHONPATH=src learnlab validate nginx/nginx-basics --format json` and
  the corresponding `nginx-nixos/nginx-basics` command: both exit 0,
  `ok: true`, empty findings.
- `git diff --check`: passed.

Initial full-suite invocation via the pytest script could not resolve the local
`tests` package during collection; the recorded successful gate uses
`python -m pytest`. Attempting `python -m learnlab` exposed the absence of a
package __main__; the successful validation gates use the installed CLI with
`PYTHONPATH=src`. Initial Ruff line-length/import findings were corrected before
the passing gate. These invocation/formatting failures are not product failures.

## Self-review and limits

Reviewed the final source/test/curriculum diffs: expected exception handling is
bounded, messages remove the catalog root, prompts agree with accepted answers,
all changed checks remain text-only, and remote commands are unchanged. The
registry remains exactly `certifications: []`; all courses remain draft and all
live checkpoints remain pending. No live/provider/SSH operations, push or merge.
The final suite establishes offline behavior only, not guest compatibility.
