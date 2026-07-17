"""Some shared state between validator and core."""

import os
from types import MappingProxyType

from shared.shared_config import SharedConfig

container_metadata: dict[str, str] = {"managed_by": "build_scheduler"}

lockfile_matrix: dict[str, str] = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}

package_managers_list: tuple[str, ...] = ("npm", "pnpm", "yarn", "bun")

valid_lockfile_list = ("pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "package-lock.json")

# Core instance identity. TODO: Change this to a public key / core uuid
#
shared_config = SharedConfig(
    CORE_ID=os.environ["CORE_ID"],
    CANCELLABLE_BUILD_STATES=set(os.environ["CANCELLABLE"].strip().split(",")),
    VALID_LOCKFILES=valid_lockfile_list,
    VALID_PMS=package_managers_list,
    CONTAINER_RUNTIME=os.environ["CONTAINER_RUNTIME"],
    CONTAINER_METADATA=MappingProxyType(container_metadata),
)
