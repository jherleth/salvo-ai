"""JSON file storage layer for Salvo run persistence.

Stores RunResult objects as JSON files under .salvo/runs/ with an
index file mapping scenario names to run IDs. Stores RunTrace objects
under .salvo/traces/ for replay. Stores TrialSuiteResult objects for
N-trial runs with latest symlink. Uses atomic writes to prevent corruption.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid7

from salvo.execution.trace import RunTrace
from salvo.models.result import RunResult
from salvo.models.trial import TrialSuiteResult
from salvo.recording.models import RecordedTrace, RevalResult, validate_trace_version


class RunStore:
    """Persist and query RunResult objects as JSON files in .salvo/.

    File layout:
        .salvo/
            runs/
                {run-id}.json    # Individual run results
            index.json           # Scenario name -> [run IDs] mapping

    Writes are atomic (write to .tmp, then rename) to prevent partial files.
    UUID7 IDs sort chronologically by default.
    """

    def __init__(self, project_root: Path, storage_dir: str | None = None) -> None:
        effective_dir = storage_dir or ".salvo"
        self.salvo_dir = project_root / effective_dir
        self.runs_dir = self.salvo_dir / "runs"
        self.traces_dir = self.salvo_dir / "traces"
        self.revals_dir = self.salvo_dir / "revals"
        self.index_path = self.salvo_dir / "index.json"

    def ensure_dirs(self) -> None:
        """Create .salvo/runs/, .salvo/traces/, and .salvo/revals/ directories."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.revals_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run_result: RunResult) -> str:
        """Save a RunResult as a JSON file and update the index.

        Args:
            run_result: The run result to persist.

        Returns:
            The run ID (either from run_result.run_id or newly generated).
        """
        self.ensure_dirs()

        # Use existing run_id or generate a new one
        run_id = run_result.run_id if run_result.run_id else str(uuid7())
        if not run_result.run_id:
            run_result = run_result.model_copy(update={"run_id": run_id})

        # Serialize to JSON
        data = run_result.model_dump(mode="json")
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Atomic write: write to .tmp then rename
        run_file = self.runs_dir / f"{run_id}.json"
        tmp_file = self.runs_dir / f"{run_id}.json.tmp"
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(run_file)

        # Update index
        scenario_name = run_result.metadata.scenario_name
        self._update_index(scenario_name, run_id)

        return run_id

    def load_run(self, run_id: str) -> RunResult:
        """Load a RunResult from its JSON file.

        Args:
            run_id: The run ID to load.

        Returns:
            The deserialized RunResult.

        Raises:
            FileNotFoundError: If no run with that ID exists.
        """
        run_file = self.runs_dir / f"{run_id}.json"
        content = run_file.read_text(encoding="utf-8")
        return RunResult.model_validate_json(content)

    def list_runs(self, scenario_name: str | None = None) -> list[str]:
        """List run IDs, optionally filtered by scenario name.

        Args:
            scenario_name: If provided, only return runs for this scenario.
                If None, return all runs sorted chronologically.

        Returns:
            Sorted list of run ID strings.
        """
        if scenario_name is not None:
            index = self._load_index()
            return index.get(scenario_name, [])

        # List all runs from disk, sorted by stem (UUID7 sorts chronologically)
        if not self.runs_dir.exists():
            return []
        return sorted(
            f.stem for f in self.runs_dir.glob("*.json")
        )

    def delete_run(self, run_id: str) -> bool:
        """Delete a run file and remove it from the index.

        Args:
            run_id: The run ID to delete.

        Returns:
            True if the run existed and was deleted, False otherwise.
        """
        run_file = self.runs_dir / f"{run_id}.json"
        existed = run_file.exists()
        if existed:
            run_file.unlink()
        self._remove_from_index(run_id)
        return existed

    def save_trace(self, run_id: str, trace: RunTrace) -> None:
        """Save a RunTrace as a JSON file in .salvo/traces/.

        Args:
            run_id: The run ID to associate the trace with.
            trace: The RunTrace to persist.
        """
        self.traces_dir.mkdir(parents=True, exist_ok=True)

        content = trace.model_dump_json(indent=2)

        # Atomic write
        trace_file = self.traces_dir / f"{run_id}.json"
        tmp_file = self.traces_dir / f"{run_id}.json.tmp"
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(trace_file)

    def load_trace(self, run_id: str) -> RunTrace | None:
        """Load a RunTrace from its JSON file.

        Args:
            run_id: The run ID whose trace to load.

        Returns:
            The deserialized RunTrace, or None if no trace exists.
        """
        trace_file = self.traces_dir / f"{run_id}.json"
        if not trace_file.exists():
            return None
        content = trace_file.read_text(encoding="utf-8")
        return RunTrace.model_validate_json(content)

    def save_suite_result(self, suite: TrialSuiteResult) -> str:
        """Save a TrialSuiteResult as a JSON file and update the index.

        Persists the entire N-trial suite result at .salvo/runs/{run_id}.json.
        Uses atomic write (write to .tmp, then rename).

        Args:
            suite: The TrialSuiteResult to persist.

        Returns:
            The run ID.
        """
        self.ensure_dirs()

        run_id = suite.run_id
        content = suite.model_dump_json(indent=2)

        # Atomic write
        run_file = self.runs_dir / f"{run_id}.json"
        tmp_file = self.runs_dir / f"{run_id}.json.tmp"
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(run_file)

        # Update index under scenario_name
        self._update_index(suite.scenario_name, run_id)

        return run_id

    def update_latest_symlink(self, run_id: str) -> None:
        """Create or update a 'latest' symlink pointing to the given run.

        Uses atomic pattern: create symlink at tmp path, then os.replace.
        Falls back to writing a .latest text file if symlinks fail (Windows).

        Args:
            run_id: The run ID to point 'latest' at.
        """
        self.ensure_dirs()
        target = f"{run_id}.json"
        link_path = self.runs_dir / "latest"

        try:
            # Atomic symlink: create tmp, then replace
            tmp_link = self.runs_dir / f".latest_tmp_{run_id}"
            # Remove stale tmp if it exists
            if tmp_link.exists() or tmp_link.is_symlink():
                tmp_link.unlink()
            os.symlink(target, tmp_link)
            os.replace(tmp_link, link_path)
        except OSError:
            # Fallback for systems without symlink support
            fallback_path = self.runs_dir / ".latest"
            fallback_path.write_text(run_id, encoding="utf-8")

    def load_suite_result(self, run_id: str) -> TrialSuiteResult:
        """Load a TrialSuiteResult from its JSON file.

        Args:
            run_id: The run ID to load.

        Returns:
            The deserialized TrialSuiteResult.

        Raises:
            FileNotFoundError: If no suite with that ID exists.
        """
        run_file = self.runs_dir / f"{run_id}.json"
        content = run_file.read_text(encoding="utf-8")
        return TrialSuiteResult.model_validate_json(content)

    def load_latest_suite(self) -> TrialSuiteResult | None:
        """Load the most recent TrialSuiteResult via the latest symlink.

        Checks for the 'latest' symlink first, then falls back to the
        '.latest' text file. Returns None if no latest exists.

        Returns:
            The deserialized TrialSuiteResult, or None.
        """
        link_path = self.runs_dir / "latest"
        fallback_path = self.runs_dir / ".latest"

        run_id: str | None = None

        if link_path.is_symlink() or link_path.exists():
            # Read symlink target filename, strip .json suffix
            target = os.readlink(link_path)
            run_id = target.removesuffix(".json")
        elif fallback_path.exists():
            run_id = fallback_path.read_text(encoding="utf-8").strip()

        if run_id is None:
            return None

        try:
            return self.load_suite_result(run_id)
        except FileNotFoundError:
            return None

    # -- Recorded trace methods --

    def save_recorded_trace(self, run_id: str, recorded: RecordedTrace) -> None:
        """Save a RecordedTrace as JSON in .salvo/traces/{run_id}.recorded.json.

        Uses atomic write pattern (write .tmp, rename).

        Args:
            run_id: The trace ID to save under.
            recorded: The RecordedTrace to persist.
        """
        self.traces_dir.mkdir(parents=True, exist_ok=True)

        content = recorded.model_dump_json(indent=2)

        # Atomic write
        trace_file = self.traces_dir / f"{run_id}.recorded.json"
        tmp_file = self.traces_dir / f"{run_id}.recorded.json.tmp"
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(trace_file)

    def load_recorded_trace(self, run_id: str) -> RecordedTrace | None:
        """Load a RecordedTrace from its JSON file.

        Returns None if not found. Validates the trace schema version
        on load.

        Args:
            run_id: The trace ID to load.

        Returns:
            The deserialized RecordedTrace, or None if not found.
        """
        trace_file = self.traces_dir / f"{run_id}.recorded.json"
        if not trace_file.exists():
            return None
        content = trace_file.read_text(encoding="utf-8")
        recorded = RecordedTrace.model_validate_json(content)
        validate_trace_version(recorded.metadata)
        return recorded

    def update_latest_recorded_symlink(self, run_id: str) -> None:
        """Create or update 'latest-recorded' symlink in .salvo/traces/.

        Uses atomic pattern: create symlink at tmp path, then os.replace.
        Falls back to writing a .latest-recorded text file if symlinks fail.

        Args:
            run_id: The trace ID to point 'latest-recorded' at.
        """
        self.ensure_dirs()
        target = f"{run_id}.recorded.json"
        link_path = self.traces_dir / "latest-recorded"

        try:
            tmp_link = self.traces_dir / f".latest_recorded_tmp_{run_id}"
            if tmp_link.exists() or tmp_link.is_symlink():
                tmp_link.unlink()
            os.symlink(target, tmp_link)
            os.replace(tmp_link, link_path)
        except OSError:
            fallback_path = self.traces_dir / ".latest-recorded"
            fallback_path.write_text(run_id, encoding="utf-8")

    def load_latest_recorded_trace(self) -> RecordedTrace | None:
        """Load the most recent RecordedTrace via the latest-recorded symlink.

        Checks for the 'latest-recorded' symlink first, then falls back
        to the '.latest-recorded' text file.

        Returns:
            The deserialized RecordedTrace, or None.
        """
        link_path = self.traces_dir / "latest-recorded"
        fallback_path = self.traces_dir / ".latest-recorded"

        run_id: str | None = None

        if link_path.is_symlink() or link_path.exists():
            target = os.readlink(link_path)
            run_id = target.removesuffix(".recorded.json")
        elif fallback_path.exists():
            run_id = fallback_path.read_text(encoding="utf-8").strip()

        if run_id is None:
            return None

        try:
            return self.load_recorded_trace(run_id)
        except FileNotFoundError:
            return None

    def list_recorded_traces(self) -> list[str]:
        """List run IDs from .salvo/traces/*.recorded.json files.

        Returns:
            Sorted list of run ID strings (chronological via UUID7).
        """
        if not self.traces_dir.exists():
            return []
        return sorted(
            f.name.removesuffix(".recorded.json")
            for f in self.traces_dir.glob("*.recorded.json")
        )

    # -- Re-evaluation result methods --

    def save_reeval_result(self, result: RevalResult) -> None:
        """Save a RevalResult as JSON in .salvo/revals/{reeval_id}.json.

        Uses atomic write pattern (write .tmp, rename). Stored separately
        from runs to avoid contaminating list_runs().

        Args:
            result: The RevalResult to persist.
        """
        self.revals_dir.mkdir(parents=True, exist_ok=True)

        content = result.model_dump_json(indent=2)

        # Atomic write
        result_file = self.revals_dir / f"{result.reeval_id}.json"
        tmp_file = self.revals_dir / f"{result.reeval_id}.json.tmp"
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(result_file)

    # -- Trace manifest methods --

    def load_trace_manifest(self) -> dict:
        """Load the trace manifest from .salvo/traces/manifest.json.

        Returns:
            Dict with schema_version and runs mapping. Returns default
            structure if file does not exist.
        """
        manifest_path = self.traces_dir / "manifest.json"
        if manifest_path.exists():
            content = manifest_path.read_text(encoding="utf-8")
            return json.loads(content)
        return {"schema_version": 1, "runs": {}}

    def update_trace_manifest(
        self,
        run_id: str,
        trace_id: str,
        trial_index: int,
        status: str,
        error: str | None = None,
        scenario_name: str = "",
    ) -> None:
        """Update the trace manifest with a new trace_id entry for a run.

        Creates the run entry if absent. Appends trace info to the run's
        trace_ids list. Uses atomic write (write .tmp, rename).

        Args:
            run_id: The run ID this trace belongs to.
            trace_id: The trace ID to register.
            trial_index: Zero-based trial index.
            status: Trial status value string.
            error: Error message if infra_error, else None.
            scenario_name: Scenario name for the run entry.
        """
        from datetime import datetime, timezone

        self.traces_dir.mkdir(parents=True, exist_ok=True)
        manifest = self.load_trace_manifest()
        runs = manifest.setdefault("runs", {})

        if run_id not in runs:
            runs[run_id] = {
                "trace_ids": [],
                "recorded": False,
                "scenario_name": scenario_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        entry: dict[str, str | int] = {
            "trace_id": trace_id,
            "trial_index": trial_index,
            "status": status,
        }
        if error is not None:
            entry["error"] = error

        runs[run_id]["trace_ids"].append(entry)

        # Atomic write
        manifest_path = self.traces_dir / "manifest.json"
        tmp_path = self.traces_dir / "manifest.json.tmp"
        content = json.dumps(manifest, indent=2, ensure_ascii=False)
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(manifest_path)

    def mark_run_recorded(self, run_id: str) -> None:
        """Mark a run as recorded in the trace manifest.

        Args:
            run_id: The run ID to mark as recorded.
        """
        manifest = self.load_trace_manifest()
        runs = manifest.get("runs", {})
        if run_id in runs:
            runs[run_id]["recorded"] = True

            # Atomic write
            manifest_path = self.traces_dir / "manifest.json"
            tmp_path = self.traces_dir / "manifest.json.tmp"
            content = json.dumps(manifest, indent=2, ensure_ascii=False)
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.rename(manifest_path)

    def get_trace_ids_for_run(self, run_id: str) -> list[str]:
        """Get all trace IDs for a given run.

        Args:
            run_id: The run ID to look up.

        Returns:
            List of trace_id strings, or empty list if run not found.
        """
        manifest = self.load_trace_manifest()
        runs = manifest.get("runs", {})
        run_entry = runs.get(run_id, {})
        return [
            entry["trace_id"]
            for entry in run_entry.get("trace_ids", [])
            if isinstance(entry, dict) and "trace_id" in entry
        ]

    def get_latest_recorded_run_id(self) -> str | None:
        """Get the most recent recorded run ID from the manifest.

        UUID7 IDs sort chronologically, so max() gives the latest.

        Returns:
            The latest recorded run_id, or None if no recorded runs exist.
        """
        manifest = self.load_trace_manifest()
        runs = manifest.get("runs", {})
        recorded_ids = [
            rid for rid, data in runs.items() if data.get("recorded", False)
        ]
        if not recorded_ids:
            return None
        return max(recorded_ids)

    def _load_index(self) -> dict[str, list[str]]:
        """Load the scenario-to-runs index file.

        Returns:
            Dict mapping scenario names to lists of run IDs.
        """
        if self.index_path.exists():
            content = self.index_path.read_text(encoding="utf-8")
            return json.loads(content)
        return {}

    def _update_index(self, scenario_name: str, run_id: str) -> None:
        """Add a run ID to the index under the given scenario name.

        Writes atomically to prevent corruption.
        """
        index = self._load_index()
        if scenario_name not in index:
            index[scenario_name] = []
        index[scenario_name].append(run_id)

        # Atomic write
        content = json.dumps(index, indent=2, ensure_ascii=False)
        tmp_path = self.index_path.with_suffix(".json.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(self.index_path)

    def _remove_from_index(self, run_id: str) -> None:
        """Remove a run ID from all scenario entries in the index.

        Writes atomically to prevent corruption.
        """
        index = self._load_index()
        changed = False
        for scenario_name in list(index.keys()):
            if run_id in index[scenario_name]:
                index[scenario_name].remove(run_id)
                changed = True
                # Remove empty scenario entries
                if not index[scenario_name]:
                    del index[scenario_name]

        if changed:
            content = json.dumps(index, indent=2, ensure_ascii=False)
            tmp_path = self.index_path.with_suffix(".json.tmp")
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.rename(self.index_path)
