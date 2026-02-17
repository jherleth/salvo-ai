---
phase: 01-foundation-and-scenario-loading
plan: 02
subsystem: loader
tags: [yaml, pydantic, validation, error-formatting, cli, pyaml, difflib]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Scenario, ToolDef, ToolParameter Pydantic models with extra='forbid'"
provides:
  - "LineTrackingLoader YAML parser with line number capture"
  - "Two-stage validation pipeline (YAML parse -> Pydantic validate)"
  - "ErrorFormatter with dual-mode output (rich Rust-style and CI concise)"
  - "salvo validate CLI command with file and directory scanning"
  - "!include tag for shared tool file resolution"
  - "Did-you-mean typo suggestions via difflib"
affects: [01-03, 02-adapter-and-runner, 03-evaluation-engine]

# Tech tracking
tech-stack:
  added: [difflib]
  patterns: [line-tracking-yaml-loader, two-stage-validation, dual-mode-error-formatting, rust-style-errors]

key-files:
  created:
    - src/salvo/loader/yaml_parser.py
    - src/salvo/loader/validator.py
    - src/salvo/loader/errors.py
    - src/salvo/cli/validate_cmd.py
    - tests/test_loader_yaml_parser.py
    - tests/test_loader_validator.py
    - tests/test_loader_errors.py
    - tests/test_cli_validate.py
  modified:
    - src/salvo/loader/__init__.py
    - src/salvo/cli/main.py

key-decisions:
  - "Used dotted path format (e.g. tools.0.name) for line_map keys to track nested YAML positions"
  - "Error codes E001-E007 mapped from Pydantic error types for consistent identification"
  - "CI mode auto-detects from CI environment variable when not explicitly set"

patterns-established:
  - "Two-stage validation: parse YAML with line tracking, then validate against Pydantic models"
  - "ErrorFormatter dual-mode: rich (Rust-style with arrows/snippets) and CI (file:line:col -- message)"
  - "!include tag for shared YAML fragments resolved relative to scenario file directory"
  - "All validation errors collected and returned at once, never one-at-a-time"
  - "Typo suggestions via difflib.get_close_matches with 0.6 cutoff"

requirements-completed: [SCEN-02]

# Metrics
duration: 5min
completed: 2026-02-17
---

# Phase 1 Plan 02: YAML Validation Pipeline and Error Formatter Summary

**Two-stage YAML validation (PyYAML line tracking -> Pydantic) with Rust-style rich error messages, CI concise output, typo suggestions, and `salvo validate` CLI command**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-17T18:28:41Z
- **Completed:** 2026-02-17T18:33:20Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- LineTrackingLoader captures 1-indexed line/column numbers for every YAML key, including nested paths under lists
- Two-stage validation pipeline: YAML parsing with line tracking feeds into Pydantic model_validate, collecting all errors in a single pass
- Rust/Elm-style rich error formatter with error codes, source snippets, arrows pointing to problems, and "did you mean?" suggestions
- CI-friendly concise output in file:line:col -- message format for automated parsers
- `salvo validate` command validates individual files or scans entire scenarios/ directory
- !include tag resolves shared tool YAML files relative to the scenario file's directory
- 32 new tests covering parser, validator, formatter, and CLI command

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for YAML parser and validator** - `9367af7` (test)
2. **Task 1 GREEN: Implement YAML parser and validation pipeline** - `f3d25b4` (feat)
3. **Task 2 RED: Failing tests for error formatter and CLI** - `698e147` (test)
4. **Task 2 GREEN: Implement error formatter and validate command** - `d259d76` (feat)

_TDD produced 2 commits per task (RED + GREEN). No refactor needed -- code was clean._

## Files Created/Modified
- `src/salvo/loader/yaml_parser.py` - LineTrackingLoader, parse_yaml_with_lines, parse_yaml_file, !include constructor
- `src/salvo/loader/validator.py` - validate_scenario_file, validate_scenario_string, ValidationErrorDetail
- `src/salvo/loader/errors.py` - ErrorFormatter with rich and CI modes, error code mapping
- `src/salvo/cli/validate_cmd.py` - salvo validate command with file/directory scanning
- `src/salvo/loader/__init__.py` - Re-exports for public API
- `src/salvo/cli/main.py` - Registered validate subcommand
- `tests/test_loader_yaml_parser.py` - 7 tests for YAML parser
- `tests/test_loader_validator.py` - 13 tests for validation pipeline
- `tests/test_loader_errors.py` - 7 tests for error formatter
- `tests/test_cli_validate.py` - 5 tests for CLI validate command

## Decisions Made
- Used dotted path format for line_map keys (e.g. "tools.0.name" -> (line, col)) for clean nested key tracking
- Mapped Pydantic error types to E001-E007 codes for consistent, scannable error identification
- CI mode auto-detects from CI environment variable as fallback when --ci flag not provided
- Error arrows point to the field name in the source line using string.find() for accurate positioning
- No refactor phase needed -- code was cleanly structured on first pass

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Validation pipeline ready for Plan 03 (project scaffolding with `salvo init`)
- `salvo validate` CLI command ready for use in generated project templates
- ErrorFormatter reusable for future CLI output (run results, comparisons)
- !include tag enables shared tool definitions across scenarios

## Self-Check: PASSED

- All 10 claimed files exist on disk
- All 4 claimed commit hashes (9367af7, f3d25b4, 698e147, d259d76) found in git log

---
*Phase: 01-foundation-and-scenario-loading*
*Completed: 2026-02-17*
