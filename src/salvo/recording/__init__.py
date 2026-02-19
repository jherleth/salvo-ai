"""Recording subpackage for trace capture and redaction.

Provides models for recorded traces, an extended redaction pipeline
with custom pattern support, and metadata_only content stripping.
"""

from salvo.recording.models import (
    CURRENT_TRACE_SCHEMA_VERSION,
    RecordedTrace,
    TraceMetadata,
    validate_trace_version,
)
from salvo.recording.redaction import (
    build_redaction_pipeline,
    strip_content_for_metadata_only,
)

__all__ = [
    "CURRENT_TRACE_SCHEMA_VERSION",
    "RecordedTrace",
    "TraceMetadata",
    "build_redaction_pipeline",
    "strip_content_for_metadata_only",
    "validate_trace_version",
]
