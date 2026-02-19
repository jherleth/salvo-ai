"""TraceRecorder orchestrating the recording pipeline.

Loads project configuration, applies custom redaction, handles
recording modes (full vs metadata_only), and persists recorded
traces via RunStore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import salvo
from salvo.recording.models import RecordedTrace, TraceMetadata
from salvo.recording.redaction import (
    apply_custom_redaction,
    build_redaction_pipeline,
    strip_content_for_metadata_only,
)

if TYPE_CHECKING:
    from salvo.models.scenario import Scenario
    from salvo.models.trial import TrialSuiteResult
    from salvo.storage.json_store import RunStore


def load_project_config(project_root: Path) -> "salvo.models.config.ProjectConfig":
    """Load ProjectConfig from salvo.yaml in the project root.

    If salvo.yaml does not exist, returns a default ProjectConfig.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Validated ProjectConfig instance.
    """
    from salvo.models.config import ProjectConfig

    config_path = project_root / "salvo.yaml"
    if not config_path.exists():
        return ProjectConfig()

    import yaml

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        return ProjectConfig()

    return ProjectConfig.model_validate(raw)


class TraceRecorder:
    """Orchestrates trace recording: redaction, mode handling, persistence.

    Records individual trial traces from a suite result, applying
    the configured redaction pipeline and recording mode before
    saving to the store.
    """

    def __init__(
        self,
        store: "RunStore",
        project_root: Path,
        recording_mode: str = "full",
        custom_patterns: list[str] | None = None,
    ) -> None:
        self.store = store
        self.project_root = project_root
        self.recording_mode = recording_mode
        self.redact_fn = build_redaction_pipeline(custom_patterns)

    def record_suite(
        self,
        suite: "TrialSuiteResult",
        scenario: "Scenario",
        scenario_file: str,
    ) -> list[str]:
        """Record all trial traces from a suite result.

        For each trial with a trace_id, loads the trace, applies
        redaction, optionally strips content for metadata_only mode,
        wraps in RecordedTrace with metadata, and persists.

        Args:
            suite: The trial suite result containing trials to record.
            scenario: The scenario that was executed.
            scenario_file: Path to the scenario YAML file.

        Returns:
            List of trace_ids that were successfully recorded.
        """
        recorded_ids: list[str] = []

        for trial in suite.trials:
            if not trial.trace_id:
                continue

            # Load the raw trace from store
            trace = self.store.load_trace(trial.trace_id)
            if trace is None:
                continue

            # Apply custom redaction
            redacted_trace = apply_custom_redaction(trace, self.redact_fn)

            # Apply metadata_only stripping if configured
            if self.recording_mode == "metadata_only":
                redacted_trace = strip_content_for_metadata_only(redacted_trace)

            # Build metadata
            metadata = TraceMetadata(
                schema_version=1,
                recording_mode=self.recording_mode,
                salvo_version=salvo.__version__,
                recorded_at=datetime.now(timezone.utc),
                source_run_id=suite.run_id,
                scenario_name=suite.scenario_name,
                scenario_file=scenario_file,
                scenario_hash=trace.scenario_hash,
            )

            # Build scenario snapshot
            scenario_snapshot = scenario.model_dump(mode="json")

            # Create RecordedTrace
            recorded = RecordedTrace(
                metadata=metadata,
                trace=redacted_trace,
                scenario_snapshot=scenario_snapshot,
            )

            # Persist
            self.store.save_recorded_trace(trial.trace_id, recorded)
            recorded_ids.append(trial.trace_id)

        # Update latest-recorded symlink to last recorded trace
        if recorded_ids:
            self.store.update_latest_recorded_symlink(recorded_ids[-1])

        return recorded_ids
