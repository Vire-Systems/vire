class ContainerCreationFail(Exception):
    """Raised when creating a container fails."""

class OutputDirNotFound(Exception):
    """Raised when the given output dir does not exist in the container."""

class ContainerAdapterAPIError(Exception):
    """General catch all error. Raise instead of raising an Exception."""