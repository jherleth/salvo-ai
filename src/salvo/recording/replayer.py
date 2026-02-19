"""TraceReplayer for loading and preparing recorded traces for display.

Provides a clean interface for loading recorded traces from the store,
either by specific run_id or the most recent recording.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.recording.models import RecordedTrace
    from salvo.storage.json_store import RunStore


class TraceReplayer:
    """Load recorded traces for replay display or re-evaluation.

    Wraps RunStore loading methods with a simplified interface.
    """

    def __init__(self, store: "RunStore") -> None:
        self.store = store

    def load(self, run_id: str | None = None) -> "RecordedTrace | None":
        """Load a recorded trace by ID, or the latest if no ID given.

        Args:
            run_id: Specific trace ID to load, or None for latest.

        Returns:
            The loaded RecordedTrace, or None if not found.
        """
        if run_id is not None:
            return self.store.load_recorded_trace(run_id)
        return self.store.load_latest_recorded_trace()

    def is_metadata_only(self, recorded: "RecordedTrace") -> bool:
        """Check if a recorded trace is in metadata_only mode.

        Args:
            recorded: The recorded trace to check.

        Returns:
            True if the trace was recorded in metadata_only mode.
        """
        return recorded.metadata.recording_mode == "metadata_only"
