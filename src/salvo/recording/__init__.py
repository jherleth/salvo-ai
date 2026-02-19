"""Recording subpackage for trace capture, redaction, and replay.

Provides models for recorded traces, an extended redaction pipeline
with custom pattern support, metadata_only content stripping,
RevalResult for re-evaluation output, and TraceReplayer for loading.
"""

from salvo.recording.models import (
    CURRENT_TRACE_SCHEMA_VERSION,
    RecordedTrace,
    RevalResult,
    TraceMetadata,
    validate_trace_version,
)
from salvo.recording.redaction import (
    build_redaction_pipeline,
    strip_content_for_metadata_only,
)
from salvo.recording.replayer import TraceReplayer

__all__ = [
    "CURRENT_TRACE_SCHEMA_VERSION",
    "RecordedTrace",
    "RevalResult",
    "TraceMetadata",
    "TraceReplayer",
    "build_redaction_pipeline",
    "strip_content_for_metadata_only",
    "validate_trace_version",
]
