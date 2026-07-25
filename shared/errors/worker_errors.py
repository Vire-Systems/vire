"""This module (errors) houses errors used by worker."""

from dataclasses import dataclass

from shared.errors.base_error import VireBaseError
from shared.utils.types import Severity


@dataclass(slots=True, kw_only=True)
class CredentialError(VireBaseError):
    """Exception used for Credential errors by worker."""

    error_title: str = (
        "Credentials for worker creation do not exist / Were not supplied"
    )
    error_code: str = "VC-IN-001"
    severity: Severity = "critical"
