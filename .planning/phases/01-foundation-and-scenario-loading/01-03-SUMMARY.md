---
phase: 01-foundation-and-scenario-loading
plan: 03
subsystem: scaffold, storage
tags: [cli, typer, rich, yaml, json, uuid7, scaffolding, persistence]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Scenario, RunResult, RunMetadata, ProjectConfig Pydantic models, CLI entry point"
  - phase: 01-02
    provides: "salvo validate command, YAML parser with !include support"
provides:
  - "scaffold_project() function generating complete Salvo project from templates"
  - "salvo init CLI command (non-interactive, --force support)"
  - "Example scenario demonstrating tool call flow with mock responses and assertions"
  - "RunStore class for JSON file I/O in .salvo/"
  - "Scenario-to-run index at .salvo/index.json"
  - "ProjectExistsError for safe file conflict detection"
affects: [02-adapter-and-runner, 03-evaluation-engine, 04-cli-and-runner, 05-llm-judge, 06-record-replay]

# Tech tracking
tech-stack:
  added: []
  patterns: [template-based-scaffolding, atomic-json-writes, uuid7-run-ids, index-file-mapping]

key-files:
  created:
    - src/salvo/scaffold/init.py
    - src/salvo/scaffold/templates/salvo.yaml
    - src/salvo/scaffold/templates/example.yaml
    - src/salvo/scaffold/templates/tools/example_tool.yaml
    - src/salvo/cli/init_cmd.py
    - src/salvo/storage/json_store.py
    - tests/test_scaffold_init.py
    - tests/test_storage_json_store.py
  modified:
    - src/salvo/cli/main.py
    - src/salvo/scaffold/__init__.py
    - src/salvo/storage/__init__.py

key-decisions:
  - "Include path in example.yaml uses ../tools/example_tool.yaml since !include resolves relative to scenario file directory"
  - "Template files stored as package data alongside init.py, located via __file__ path"
  - "RunStore uses Python 3.14 builtin uuid.uuid7() for chronologically-sortable run IDs"
  - "Atomic writes via write-to-tmp-then-rename pattern for both run files and index"

patterns-established:
  - "Template-based project scaffolding with file map and conflict detection"
  - "Atomic JSON persistence with .tmp file then rename"
  - "Index file pattern: flat JSON mapping scenario names to lists of run IDs"
  - "ProjectExistsError with conflicting_files attribute for user-friendly error messages"

requirements-completed: [CLI-01, CLI-05]

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 1 Plan 03: Project Scaffolding and JSON Storage Summary

**`salvo init` project scaffolding with template-based generation (config, example scenario with tool call flow, shared tool file) plus RunStore JSON persistence layer with atomic writes and scenario-to-run indexing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17T18:35:56Z
- **Completed:** 2026-02-17T18:40:20Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- `salvo init` generates a complete working project: salvo.yaml config, example scenario with 4 tools and 4 assertion types, shared tool file via !include, and .gitignore
- Example scenario demonstrates the full tool call flow pattern (read file, find bug, write fix, run tests) with mock responses and weighted assertions
- RunStore persists RunResult objects as JSON in .salvo/runs/ with atomic writes and a scenario-to-run index
- 28 new tests covering scaffolding, CLI commands, .gitignore handling, storage CRUD, index integrity, and round-trip serialization

## Task Commits

Each task was committed atomically:

1. **Task 1: salvo init scaffolding with templates** - `1dddff6` (feat)
2. **Task 2: JSON storage layer for .salvo/ directory** - `b39dab1` (feat)

## Files Created/Modified
- `src/salvo/scaffold/init.py` - scaffold_project() with file map, conflict detection, .gitignore handling
- `src/salvo/scaffold/templates/salvo.yaml` - Default project config template
- `src/salvo/scaffold/templates/example.yaml` - Full example scenario with 4 tools, 4 assertions, tool call flow story
- `src/salvo/scaffold/templates/tools/example_tool.yaml` - Shared tool definition (list_files) for !include demo
- `src/salvo/cli/init_cmd.py` - salvo init command with directory arg and --force flag
- `src/salvo/cli/main.py` - Registered init command alongside validate
- `src/salvo/scaffold/__init__.py` - Re-exports scaffold_project and ProjectExistsError
- `src/salvo/storage/json_store.py` - RunStore with save/load/list/delete, atomic writes, index management
- `src/salvo/storage/__init__.py` - Re-exports RunStore
- `tests/test_scaffold_init.py` - 14 tests for scaffolding and CLI
- `tests/test_storage_json_store.py` - 14 tests for storage layer

## Decisions Made
- Template !include path uses `../tools/example_tool.yaml` because the !include resolver (from Plan 02) resolves relative to the scenario file's parent directory, not the project root
- Template files are located via `Path(__file__).parent / "templates"` for reliable package-relative resolution
- Used Python 3.14's builtin `uuid.uuid7()` directly (no fallback needed since project requires Python 3.10+ and uuid7 package is installed)
- RunStore creates directories lazily on first save rather than requiring explicit initialization

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed !include path in example.yaml template**
- **Found during:** Task 1 (integration test)
- **Issue:** Template used `!include tools/example_tool.yaml` but the !include resolver from Plan 02 resolves paths relative to the scenario file's directory (`scenarios/`), causing FileNotFoundError at `scenarios/tools/example_tool.yaml`
- **Fix:** Changed include path to `../tools/example_tool.yaml` so it resolves correctly from `scenarios/` up to project root then into `tools/`
- **Files modified:** src/salvo/scaffold/templates/example.yaml
- **Verification:** `salvo init` followed by `salvo validate` on generated example.yaml passes
- **Committed in:** 1dddff6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for generated projects to pass validation. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 complete: all 3 plans executed successfully
- Full scenario loading pipeline ready: models (01-01), validation (01-02), scaffolding + storage (01-03)
- `salvo init` creates valid projects that pass `salvo validate`
- RunStore ready for Phase 2 (adapter/runner) to persist execution results
- 85 total tests passing across all Phase 1 plans

## Self-Check: PASSED

- All 11 claimed files exist on disk
- All 2 claimed commit hashes (1dddff6, b39dab1) found in git log

---
*Phase: 01-foundation-and-scenario-loading*
*Completed: 2026-02-17*
