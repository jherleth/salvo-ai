---
phase: 01-foundation-and-scenario-loading
plan: 01
subsystem: models
tags: [pydantic, python, cli, typer, data-models]

# Dependency graph
requires: []
provides:
  - "Scenario, ToolDef, ToolParameter, Assertion Pydantic models"
  - "RunResult, EvalResult, RunMetadata Pydantic models"
  - "ProjectConfig Pydantic model"
  - "salvo-ai pip-installable package skeleton"
  - "salvo CLI entry point with --version"
affects: [01-02, 01-03, 02-adapter-and-runner, 03-evaluation-engine]

# Tech tracking
tech-stack:
  added: [pydantic v2, typer, rich, pyyaml, uuid7, hatchling, pytest]
  patterns: [src-layout, extra-forbid-models, pydantic-v2-model-validate]

key-files:
  created:
    - pyproject.toml
    - src/salvo/__init__.py
    - src/salvo/models/__init__.py
    - src/salvo/models/scenario.py
    - src/salvo/models/result.py
    - src/salvo/models/config.py
    - src/salvo/cli/main.py
    - tests/test_models_scenario.py
    - tests/test_models_result.py
    - tests/test_models_config.py
  modified:
    - .gitignore

key-decisions:
  - "Used hatchling build backend with src/ layout for clean package structure"
  - "All models use extra='forbid' to reject unknown YAML keys early"
  - "Created venv for isolated development (Python 3.14 externally-managed)"

patterns-established:
  - "extra='forbid' on all Pydantic models to catch YAML typos"
  - "Model re-exports from salvo.models.__init__ for clean imports"
  - "TDD RED-GREEN-REFACTOR cycle with atomic commits per phase"
  - "src/ layout with hatchling for pip-installable package"

requirements-completed: [SCEN-01, SCEN-03]

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 1 Plan 01: Package Skeleton and Data Models Summary

**Pydantic v2 data models (Scenario, RunResult, ProjectConfig) with extra='forbid' validation, pip-installable salvo-ai package, and Typer CLI entry point**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17T18:22:26Z
- **Completed:** 2026-02-17T18:26:05Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- Pip-installable `salvo-ai` package with hatchling build and src/ layout
- Typed Pydantic v2 models for Scenario (YAML contract), RunResult (execution output), and ProjectConfig (project settings)
- All models enforce `extra='forbid'` to reject unknown YAML keys at parse time
- 25 comprehensive tests covering validation, defaults, type constraints, and JSON round-trip serialization
- `salvo` CLI entry point with `--version` flag via Typer

## Task Commits

Each task was committed atomically:

1. **Task 1: Create package skeleton and pyproject.toml** - `40312c3` (feat)
2. **Task 2 RED: Failing tests for data models** - `ccefa4b` (test)
3. **Task 2 GREEN: Implement Pydantic models** - `811dfeb` (feat)

_TDD Task 2 produced 2 commits (RED + GREEN). No refactor needed -- code was clean._

## Files Created/Modified
- `pyproject.toml` - Package config with hatchling build, dependencies, CLI entry point
- `src/salvo/__init__.py` - Package root with __version__
- `src/salvo/models/scenario.py` - Scenario, ToolDef, ToolParameter, Assertion models
- `src/salvo/models/result.py` - RunMetadata, EvalResult, RunResult models
- `src/salvo/models/config.py` - ProjectConfig model
- `src/salvo/models/__init__.py` - Re-exports all 8 public model classes
- `src/salvo/cli/main.py` - Minimal Typer app with --version callback
- `src/salvo/loader/__init__.py` - Empty loader subpackage placeholder
- `src/salvo/storage/__init__.py` - Empty storage subpackage placeholder
- `src/salvo/scaffold/__init__.py` - Empty scaffold subpackage placeholder
- `src/salvo/cli/__init__.py` - Empty CLI subpackage
- `tests/__init__.py` - Test package
- `tests/test_models_scenario.py` - 14 tests for scenario models
- `tests/test_models_result.py` - 8 tests for result models
- `tests/test_models_config.py` - 3 tests for config model
- `.gitignore` - Added venv, __pycache__, .salvo/ exclusions

## Decisions Made
- Used hatchling as build backend (modern, well-supported, matches pyproject.toml standard)
- Created `.venv` virtual environment since macOS Python 3.14 is externally-managed (PEP 668)
- Build backend path is `hatchling.build` (not `hatchling.backends` as initially specified in plan)
- No refactor phase needed -- models were clean and minimal on first implementation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hatchling build-backend path**
- **Found during:** Task 1 (package install)
- **Issue:** Plan specified `hatchling.backends` but correct module path is `hatchling.build`
- **Fix:** Changed build-backend to `"hatchling.build"` in pyproject.toml
- **Files modified:** pyproject.toml
- **Verification:** `pip install -e ".[dev]"` succeeded
- **Committed in:** 40312c3 (Task 1 commit)

**2. [Rule 3 - Blocking] Created virtual environment for isolated install**
- **Found during:** Task 1 (package install)
- **Issue:** macOS Python 3.14 is externally-managed (PEP 668), pip refused system-wide install
- **Fix:** Created `.venv` with `python3 -m venv .venv`, all subsequent commands use activated venv
- **Files modified:** .gitignore (added .venv/ exclusion)
- **Verification:** Package installed successfully in venv
- **Committed in:** 40312c3 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were necessary for the package to install. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All data models ready for import by Plans 02 (YAML loader) and 03 (project scaffolding)
- Package skeleton has placeholder subpackages for loader, storage, scaffold
- pytest infrastructure configured and working
- CLI entry point ready for subcommand addition in subsequent plans

## Self-Check: PASSED

- All 15 claimed files exist on disk
- All 3 claimed commit hashes (40312c3, ccefa4b, 811dfeb) found in git log

---
*Phase: 01-foundation-and-scenario-loading*
*Completed: 2026-02-17*
