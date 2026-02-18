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

    def __init__(self, project_root: Path) -> None:
        self.salvo_dir = project_root / ".salvo"
        self.runs_dir = self.salvo_dir / "runs"
        self.traces_dir = self.salvo_dir / "traces"
        self.index_path = self.salvo_dir / "index.json"

    def ensure_dirs(self) -> None:
        """Create .salvo/runs/ and .salvo/traces/ directory structure."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)

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
