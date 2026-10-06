"""Session-source boundary and concrete supported OpenCode adapters."""
from .base import LiveSessionSource, SessionSource, SourceChange
from .discovery import (
    DatabaseCandidate,
    ServiceRegistration,
    ServiceRegistrationCandidate,
    ServiceRegistrationError,
    default_opencode_data_dir,
    default_opencode_state_dir,
    discover_v1_database_candidate,
    discover_v2_registration_candidate,
    read_v2_service_registration,
)
from .errors import (
    SourceDataError,
    SourceError,
    SourceResyncRequiredError,
    SourceSchemaError,
    SourceUnavailableError,
)
from .model_availability import ModelAvailabilitySource, OpenCodeModelAvailabilitySource
from .opencode_v1 import OpenCodeV1Source, V1SchemaInfo
from .opencode_v2 import OpenCodeV2Source, V2Endpoint
from .selection import MigrationGapDiagnostic, SourceSelection, SourceSelector, inspect_v1_v2_migration_gap

__all__ = [
    "DatabaseCandidate", "LiveSessionSource", "MigrationGapDiagnostic", "ModelAvailabilitySource",
    "OpenCodeModelAvailabilitySource", "OpenCodeV1Source",
    "OpenCodeV2Source", "ServiceRegistration", "ServiceRegistrationCandidate",
    "ServiceRegistrationError", "SessionSource", "SourceChange", "SourceDataError", "SourceError",
    "SourceResyncRequiredError", "SourceSchemaError", "SourceSelection", "SourceSelector",
    "SourceUnavailableError", "V1SchemaInfo", "V2Endpoint", "default_opencode_data_dir",
    "default_opencode_state_dir", "discover_v1_database_candidate", "discover_v2_registration_candidate",
    "inspect_v1_v2_migration_gap", "read_v2_service_registration",
]
