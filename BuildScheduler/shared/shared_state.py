"""Some shared state between validator and core."""

import os

package_managers = ["npm", "pnpm", "yarn", "bun"]

lockfile_matrix = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun"
}

valid_lockfiles = ["pnpm-lock.yaml","yarn.lock","bun.lock", "bun.lockb","package-lock.json"]

# Core instance identity. TODO: Change this to a public key / core uuid
core_id = os.getenv("CORE_ID")
assert core_id is not None


# Cancellable state
cancellable_builds_str = os.getenv("CANCELLABLE")

assert cancellable_builds_str is not None, "Cannot fetch cancellable build states"
cancellable_build_states: set[str] = set(cancellable_builds_str.strip().split(','))
print(cancellable_build_states)