"""Tests for the JSON storage layer (RunStore)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid7

import pytest

from salvo.models.result import EvalResult, RunMetadata, RunResult
from salvo.storage.json_store import RunStore


def _make_run_result(
    scenario_name: str = "test-scenario",
    run_id: str | None = None,
    score: float = 0.85,
    passed: bool = True,
    cost_usd: float = 0.0042,
    latency_seconds: float = 1.23,
) -> RunResult:
    """Build a valid RunResult with realistic field values."""
    return RunResult(
        run_id=run_id or str(uuid7()),
        metadata=RunMetadata(
            scenario_name=scenario_name,
            scenario_file=f"scenarios/{scenario_name}.yaml",
            scenario_hash="abc123def456",
            timestamp=datetime.now(timezone.utc),
            model="gpt-4o",
            adapter="openai",
            salvo_version="0.1.0",
            passed=passed,
            score=score,
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
        ),
        eval_results=[
            EvalResult(
                assertion_type="tool_called",
                score=1.0,
                passed=True,
                weight=1.0,
                required=True,
                details="Tool file_read was called",
            ),
        ],
        score=score,
        passed=passed,
    )


class TestRunStoreEnsureDirs:
    """Tests for directory creation."""

    def test_creates_salvo_runs_directory(self, tmp_path: Path) -> None:
        """ensure_dirs creates .salvo/runs/ directory."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        assert (tmp_path / ".salvo" / "runs").is_dir()


class TestRunStoreSave:
    """Tests for saving runs."""

    def test_save_creates_json_file_and_returns_uuid(self, tmp_path: Path) -> None:
        """save_run creates a JSON file in .salvo/runs/ and returns a valid UUID string."""
        store = RunStore(tmp_path)
        run = _make_run_result()
        run_id = store.save_run(run)
        assert isinstance(run_id, str)
        assert len(run_id) > 0
        assert (tmp_path / ".salvo" / "runs" / f"{run_id}.json").exists()

    def test_save_updates_index_file(self, tmp_path: Path) -> None:
        """Saving a run updates the index file at .salvo/index.json."""
        store = RunStore(tmp_path)
        run = _make_run_result(scenario_name="my-scenario")
        run_id = store.save_run(run)
        index_path = tmp_path / ".salvo" / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert "my-scenario" in index
        assert run_id in index["my-scenario"]

    def test_index_structure(self, tmp_path: Path) -> None:
        """Index file structure: {"scenario_name": ["run-id-1", "run-id-2"]}."""
        store = RunStore(tmp_path)
        run1 = _make_run_result(scenario_name="scenario-a")
        run2 = _make_run_result(scenario_name="scenario-a")
        id1 = store.save_run(run1)
        id2 = store.save_run(run2)
        index = json.loads(
            (tmp_path / ".salvo" / "index.json").read_text(encoding="utf-8")
        )
        assert index == {"scenario-a": [id1, id2]}

    def test_no_tmp_files_after_save(self, tmp_path: Path) -> None:
        """No .tmp files left behind after save (atomic write)."""
        store = RunStore(tmp_path)
        run = _make_run_result()
        store.save_run(run)
        runs_dir = tmp_path / ".salvo" / "runs"
        tmp_files = list(runs_dir.glob("*.tmp"))
        assert tmp_files == []
        # Also check index tmp
        salvo_dir = tmp_path / ".salvo"
        index_tmps = list(salvo_dir.glob("*.tmp"))
        assert index_tmps == []

    def test_multiple_runs_same_scenario_in_index(self, tmp_path: Path) -> None:
        """Multiple runs for the same scenario all appear in the index."""
        store = RunStore(tmp_path)
        ids = []
        for _ in range(3):
            run = _make_run_result(scenario_name="repeated")
            ids.append(store.save_run(run))
        index = json.loads(
            (tmp_path / ".salvo" / "index.json").read_text(encoding="utf-8")
        )
        assert index["repeated"] == ids


class TestRunStoreLoad:
    """Tests for loading runs."""

    def test_round_trip_equality(self, tmp_path: Path) -> None:
        """load_run returns a RunResult equal to what was saved."""
        store = RunStore(tmp_path)
        original = _make_run_result()
        run_id = store.save_run(original)
        loaded = store.load_run(run_id)
        assert loaded.run_id == run_id
        assert loaded.score == original.score
        assert loaded.passed == original.passed
        assert loaded.metadata.scenario_name == original.metadata.scenario_name
        assert loaded.metadata.model == original.metadata.model
        assert len(loaded.eval_results) == len(original.eval_results)

    def test_nonexistent_run_raises_error(self, tmp_path: Path) -> None:
        """load_run with nonexistent run_id raises FileNotFoundError."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        with pytest.raises(FileNotFoundError):
            store.load_run("nonexistent-id")

    def test_metadata_fields_survive_round_trip(self, tmp_path: Path) -> None:
        """Metadata fields (timestamp, cost_usd, latency_seconds) survive JSON round-trip."""
        store = RunStore(tmp_path)
        original = _make_run_result(cost_usd=0.0042, latency_seconds=2.567)
        run_id = store.save_run(original)
        loaded = store.load_run(run_id)

        # Timestamp serialized as ISO string and back
        assert loaded.metadata.timestamp == original.metadata.timestamp
        # Floats preserved
        assert loaded.metadata.cost_usd == pytest.approx(0.0042)
        assert loaded.metadata.latency_seconds == pytest.approx(2.567)


class TestRunStoreList:
    """Tests for listing runs."""

    def test_list_all_runs_sorted(self, tmp_path: Path) -> None:
        """list_runs() with no filter returns all saved run IDs in sorted order."""
        store = RunStore(tmp_path)
        ids = []
        for name in ["a-scenario", "b-scenario", "c-scenario"]:
            run = _make_run_result(scenario_name=name)
            ids.append(store.save_run(run))
        all_runs = store.list_runs()
        assert len(all_runs) == 3
        assert all_runs == sorted(all_runs)

    def test_list_runs_by_scenario(self, tmp_path: Path) -> None:
        """list_runs(scenario_name="test") returns only runs for that scenario."""
        store = RunStore(tmp_path)
        target_ids = []
        for _ in range(2):
            run = _make_run_result(scenario_name="target")
            target_ids.append(store.save_run(run))
        # Add a different scenario
        store.save_run(_make_run_result(scenario_name="other"))

        result = store.list_runs(scenario_name="target")
        assert result == target_ids

    def test_list_runs_empty_scenario(self, tmp_path: Path) -> None:
        """list_runs for a scenario with no runs returns empty list."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        result = store.list_runs(scenario_name="nonexistent")
        assert result == []


class TestRunStoreDelete:
    """Tests for deleting runs."""

    def test_delete_removes_file_and_index(self, tmp_path: Path) -> None:
        """delete_run removes the JSON file and removes from index."""
        store = RunStore(tmp_path)
        run = _make_run_result(scenario_name="deletable")
        run_id = store.save_run(run)

        assert store.delete_run(run_id) is True
        assert not (tmp_path / ".salvo" / "runs" / f"{run_id}.json").exists()

        # Index should no longer reference this run
        index = json.loads(
            (tmp_path / ".salvo" / "index.json").read_text(encoding="utf-8")
        )
        assert "deletable" not in index  # Removed empty entry

    def test_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """delete_run on nonexistent run returns False."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        assert store.delete_run("nonexistent") is False
