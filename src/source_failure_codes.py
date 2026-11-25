"""Stable source failure categories readable without loading source adapters."""
from enum import StrEnum


class FailureCode(StrEnum):
    UNKNOWN = "unknown_source_failure"
    REGISTRATION_MISSING = "registration_missing"
    REGISTRATION_INVALID = "registration_invalid"
    REGISTRATION_UNREADABLE = "registration_unreadable"
    ENDPOINT_UNRESPONSIVE = "endpoint_unresponsive"
    REFUSED = "connection_refused"
    RESET = "connection_reset"
    DISCONNECTED = "connection_disconnected"
    TIMEOUT = "connection_timeout"
    AUTH = "http_auth_failure"
    HTTP = "http_status_failure"
    VERSION = "unsupported_version"
    SCHEMA = "unsupported_schema"
    DATA = "invalid_data"
    CONCURRENT = "concurrent_source_change"
    V1_MISSING = "v1_database_missing"
    V1_UNREADABLE = "v1_database_unreadable"
