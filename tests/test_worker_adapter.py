"""
Integration tests for:
  - BuildScheduler/worker/utils/adapter.py  (FRAMEWORK_REGISTRY, FrameworkAdapter)
  - BuildScheduler/worker/core/create_container_job.py  (setup_creation)
  - BuildScheduler/worker/cli_parser.py  (load_parser — tested via direct JSON parsing)
  - BuildScheduler/worker/schema/worker_dataclasses.py  (WorkerContext, WorkerConfig, FrameworkAdapter)

Covers:
  - FRAMEWORK_REGISTRY is correctly populated
  - FrameworkAdapter exposes image, install_command, build_command
  - setup_creation constructs correct shell commands with/without install_req
  - setup_creation raises KeyError for unsupported framework
  - WorkerConfig raises ValueError if any field is None
  - WorkerContext is a frozen, slotted dataclass
"""

import uuid
from unittest.mock import patch

import pytest


# ── FrameworkAdapter / FRAMEWORK_REGISTRY tests ───────────────────────────────

class TestFrameworkRegistry:
    """Verify the adapter registry and FrameworkAdapter defaults."""

    def test_vite_is_in_registry(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        assert "vite" in FRAMEWORK_REGISTRY

    def test_vite_adapter_has_correct_image(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        assert vite.image == "vire-runner:node22"

    def test_vite_npm_build_command(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        assert vite.build_command["npm"] == "npm run build"

    def test_vite_pnpm_build_command(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        assert vite.build_command["pnpm"] == "pnpm run build"

    def test_vite_npm_install_command(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        assert vite.install_command["npm"] == "npm ci --ignore-scripts"

    def test_vite_pnpm_install_command(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        assert vite.install_command["pnpm"] == "pnpm install --frozen-lockfile --ignore-scripts"

    def test_unsupported_framework_raises_key_error(self):
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        with pytest.raises(KeyError):
            _ = FRAMEWORK_REGISTRY["rails"]

    def test_framework_adapter_is_frozen(self):
        """FrameworkAdapter is frozen=True — attribute assignment should raise."""
        from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
        vite = FRAMEWORK_REGISTRY["vite"]
        with pytest.raises((AttributeError, TypeError)):
            vite.image = "some-other-image"  # type: ignore[misc]


# ── WorkerContext / WorkerConfig dataclass tests ──────────────────────────────

class TestWorkerContext:
    """WorkerContext is a frozen, slotted dataclass."""

    def _make(self, **kwargs):
        from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
        defaults = dict(
            job_uuid=str(uuid.uuid4()),
            user_uuid=str(uuid.uuid4()),
            remote="https://github.com/acme/frontend.git",
            repo_name="frontend",
            framework="vite",
            package_manager="npm",
            install_req=True,
            OUTPUT_DIR="dist",
            COMMIT_ID="deadbeef1234",
        )
        defaults.update(kwargs)
        return WorkerContext(**defaults)

    def test_can_be_created(self):
        wc = self._make()
        assert wc.framework == "vite"
        assert wc.package_manager == "npm"

    def test_is_frozen(self):
        wc = self._make()
        with pytest.raises((AttributeError, TypeError)):
            wc.framework = "next"  # type: ignore[misc]

    def test_install_req_false(self):
        wc = self._make(install_req=False)
        assert wc.install_req is False


class TestWorkerConfig:
    """WorkerConfig raises ValueError if any field is None via __post_init__."""

    def _make(self, **overrides):
        from BuildScheduler.worker.schema.worker_dataclasses import WorkerConfig
        defaults = dict(
            CONTAINER_EXPIRY=300,
            CONTAINER_RUNTIME="docker",
            REDIS_URL="redis://localhost:6379",
            WORKER_OUTPUT_DIR="/tmp/output",
            WORKER_LOGDIR="/tmp/logs",
            DB_FILE="/tmp/test.db",
        )
        defaults.update(overrides)
        return WorkerConfig(**defaults)

    def test_valid_config_is_created(self):
        cfg = self._make()
        assert cfg.CONTAINER_EXPIRY == 300
        assert cfg.CONTAINER_RUNTIME == "docker"

    def test_none_field_raises_value_error(self):
        with pytest.raises(ValueError, match="cannot be 'None'"):
            self._make(REDIS_URL=None)

    def test_none_db_file_raises_value_error(self):
        with pytest.raises(ValueError, match="cannot be 'None'"):
            self._make(DB_FILE=None)

    def test_none_worker_output_dir_raises(self):
        with pytest.raises(ValueError, match="cannot be 'None'"):
            self._make(WORKER_OUTPUT_DIR=None)


# ── setup_creation tests ──────────────────────────────────────────────────────

class TestSetupCreation:
    """setup_creation constructs the container image and shell command string."""

    def _make_worker_context(self, install_req=True, pm="npm", framework="vite"):
        from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
        return WorkerContext(
            job_uuid=str(uuid.uuid4()),
            user_uuid=str(uuid.uuid4()),
            remote="https://github.com/acme/frontend.git",
            repo_name="frontend",
            framework=framework,
            package_manager=pm,
            install_req=install_req,
            OUTPUT_DIR="dist",
            COMMIT_ID="abc123sha",
        )

    def test_returns_tuple_of_image_and_cmd(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context()
        image, cmd = setup_creation(wc)

        assert isinstance(image, str)
        assert isinstance(cmd, str)

    def test_image_is_correct(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context()
        image, _ = setup_creation(wc)

        assert image == "vire-runner:node22"

    def test_cmd_contains_git_clone(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context()
        _, cmd = setup_creation(wc)

        assert "git clone" in cmd
        assert wc.remote in cmd

    def test_cmd_contains_git_checkout(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context()
        _, cmd = setup_creation(wc)

        assert "git checkout" in cmd
        assert wc.COMMIT_ID in cmd

    def test_cmd_contains_build_command_npm(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="npm", install_req=False)
        _, cmd = setup_creation(wc)

        assert "npm run build" in cmd

    def test_cmd_contains_build_command_pnpm(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="pnpm", install_req=False)
        _, cmd = setup_creation(wc)

        assert "pnpm run build" in cmd

    def test_cmd_includes_install_when_install_req_true(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="npm", install_req=True)
        _, cmd = setup_creation(wc)

        assert "npm ci --ignore-scripts" in cmd

    def test_cmd_excludes_install_when_install_req_false(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="npm", install_req=False)
        _, cmd = setup_creation(wc)

        assert "npm ci" not in cmd

    def test_cmd_includes_pnpm_install_when_required(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="pnpm", install_req=True)
        _, cmd = setup_creation(wc)

        assert "pnpm install --frozen-lockfile --ignore-scripts" in cmd

    def test_unsupported_framework_raises_key_error(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(framework="unsupported-fw-xyz")
        with pytest.raises(KeyError):
            setup_creation(wc)

    def test_cmd_contains_cd_into_repo(self):
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context()
        _, cmd = setup_creation(wc)

        assert f"cd {wc.repo_name}" in cmd

    def test_command_ordering_is_correct(self):
        """
        The full command must follow this order:
          git clone → cd repo_name → git checkout commit_id [→ install] → build
        """
        from BuildScheduler.worker.core.create_container_job import setup_creation

        wc = self._make_worker_context(pm="npm", install_req=True)
        _, cmd = setup_creation(wc)

        clone_pos    = cmd.index("git clone")
        cd_pos       = cmd.index(f"cd {wc.repo_name}")
        checkout_pos = cmd.index("git checkout")
        install_pos  = cmd.index("npm ci")
        build_pos    = cmd.index("npm run build")

        assert clone_pos < cd_pos < checkout_pos < install_pos < build_pos


# ── CLI parser: direct JSON struct parsing tests ──────────────────────────────

class TestCliParserJsonParsing:
    """
    load_parser() calls argparse.parse_args() which reads sys.argv — not suitable
    for unit tests as-is. However, the core logic (JSON → WorkerContext) can be
    exercised by testing the JSON parsing portion directly.
    """

    def test_valid_json_struct_creates_worker_context(self):
        """
        Simulate what load_parser does with the json_struct argument.
        This tests the JSON → WorkerContext mapping without argparse I/O.
        """
        import json
        from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext

        json_struct = {
            "job_uuid": "job-aaa",
            "user_uuid": "user-bbb",
            "remote": "https://github.com/acme/frontend.git",
            "repo_name": "frontend",
            "framework": "vite",
            "pm": "npm",
            "install_req": True,
            "output_dir": "dist",
            "commit_id": "abc123sha",
        }

        # Reproduce the WorkerContext construction from load_parser
        state = WorkerContext(
            job_uuid=json_struct["job_uuid"],
            user_uuid=json_struct["user_uuid"],
            remote=json_struct["remote"],
            repo_name=json_struct["repo_name"],
            framework=json_struct["framework"],
            package_manager=json_struct["pm"],
            install_req=json_struct["install_req"],
            OUTPUT_DIR=json_struct["output_dir"],
            COMMIT_ID=json_struct["commit_id"],
        )

        assert state.job_uuid == "job-aaa"
        assert state.framework == "vite"
        assert state.package_manager == "npm"
        assert state.install_req is True

    def test_missing_key_raises_key_error(self):
        """Missing 'pm' key in json_struct should cause a KeyError → CredentialError."""
        from shared.errors.worker_errors import CredentialError
        from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext

        bad_struct = {
            "job_uuid": "job-aaa",
            "user_uuid": "user-bbb",
            "remote": "https://github.com/acme/frontend.git",
            "repo_name": "frontend",
            "framework": "vite",
            # 'pm' is missing
            "install_req": True,
            "output_dir": "dist",
            "commit_id": "abc123sha",
        }

        with pytest.raises(KeyError):
            WorkerContext(
                job_uuid=bad_struct["job_uuid"],
                user_uuid=bad_struct["user_uuid"],
                remote=bad_struct["remote"],
                repo_name=bad_struct["repo_name"],
                framework=bad_struct["framework"],
                package_manager=bad_struct["pm"],  # KeyError here
                install_req=bad_struct["install_req"],
                OUTPUT_DIR=bad_struct["output_dir"],
                COMMIT_ID=bad_struct["commit_id"],
            )


# ── WorkerCreationParams dataclass tests ─────────────────────────────────────

class TestWorkerCreationParams:
    """WorkerCreationParams should be a frozen dataclass matching BuildData fields."""

    def test_wcp_is_frozen(self):
        from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams

        wcp = WorkerCreationParams(
            job_uuid="job-aaa",
            user_uuid="user-bbb",
            remote_link="https://github.com/acme/frontend.git",
            commit_id="abc123sha",
            repo_name="frontend",
            framework="vite",
            pm="npm",
            install_req=True,
            output_dir="dist",
        )

        with pytest.raises((AttributeError, TypeError)):
            wcp.framework = "next"  # type: ignore[misc]

    def test_wcp_fields_are_accessible(self):
        from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams

        wcp = WorkerCreationParams(
            job_uuid="job-001",
            user_uuid="user-001",
            remote_link="https://github.com/acme/frontend.git",
            commit_id="sha256abc",
            repo_name="frontend",
            framework="vite",
            pm="pnpm",
            install_req=False,
            output_dir="build",
        )

        assert wcp.pm == "pnpm"
        assert wcp.install_req is False
        assert wcp.output_dir == "build"
