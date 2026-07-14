"""Some shared state between validator and core."""

import os
from BuildScheduler.shared.shared_config import SharedConfig
from types import MappingProxyType


container_metadata: dict[str, str] = {
    "managed_by": "build_scheduler"
}

lockfile_matrix = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun"
}

package_managers_list = (
    "npm",
    "pnpm",
    "yarn",
    "bun"
)

valid_lockfile_list = (
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "package-lock.json"
)

# Core instance identity. TODO: Change this to a public key / core uuid
# 
shared_config = SharedConfig(
    CORE_ID= os.environ["CORE_ID"],
    CANCELLABLE_BUILD_STATES = set(os.environ["CANCELLABLE"].strip().split(',')),
    VALID_LOCKFILES = valid_lockfile_list,
    VALID_PMS=package_managers_list,
    CONTAINER_RUNTIME=os.environ["CONTAINER_RUNTIME"],
    CONTAINER_METADATA = MappingProxyType(container_metadata)
)