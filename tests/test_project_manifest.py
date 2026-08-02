"""
Integration tests for Vire/project_manifest/ and Vire/core/validate/*.

Covers:
  - parse_toml.parse_toml (valid + invalid TOML)
  - schema_check.check_toml_schema (valid schema / missing keys / missing tables)
  - validator.validate_package_json (blocked keys / clean json / malformed json)
  - validator.validate_toml (framework / lockfile / output_dir validation)
  - parse_vire_toml.parse_vire_toml (toml fetch + parse in one flow)
  - validate_lockfile.validate_lockfile (pm validation + lockfile fetch)
  - validate_vire_toml.validate_vire_toml (passes valid PTO / raises on bad toml)
  - resolve_packagejson.validate_pkgjson (passes valid / fails on blocked keys)

External dependencies patched:
  - Vire.core.core_utils.fetch_buildreq.send_request   (HTTP calls)
  - shared.logging.scheduler_logger.vire_logger
  - shared.logging.pub_redis.publish_log_redis
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_LOGGER  = "shared.event_handling.handler.vire_logger"
PATCH_REDIS   = "shared.event_handling.state_propagation.publish_log_redis"
PATCH_REQUEST = "Vire.core.core_utils.fetch_buildreq.send_request"
PATCH_REQUEST_LOCKFILE_VALIDATION = "Vire.core.core_utils.fetch_lockfile.send_request"

# ─── helpers ──────────────────────────────────────────────────────────────────

VALID_TOML = """
[details]
framework = "vite"
package_manager = "npm"

[project]
output_dir = "dist"
framework_version = "5.0"
dependencies = true
"""

MISSING_DETAILS_TOML = """
[project]
output_dir = "dist"
framework_version = "5.0"
dependencies = true
"""

MISSING_PROJECT_TOML = """
[details]
framework = "vite"
package_manager = "npm"
"""

MISSING_FIELD_TOML = """
[details]
framework = "vite"

[project]
output_dir = "dist"
framework_version = "5.0"
dependencies = true
"""

INVALID_TOML_SYNTAX = "[[[ not valid toml ]]"

CLEAN_PACKAGE_JSON = """
{
  "name": "my-app",
  "scripts": {
    "build": "vite build",
    "preview": "vite preview"
  }
}
"""

BLOCKED_PACKAGE_JSON = """
{
  "name": "my-app",
  "scripts": {
    "build": "vite build",
    "postinstall": "malicious script"
  }
}
"""

START_SCRIPT_PACKAGE_JSON = """
{
  "name": "my-app",
  "scripts": {
    "start": "node server.js",
    "build": "vite build"
  }
}
"""


def make_validator_context(
    job_uuid="job-aaa",
    user_uuid="user-bbb",
    provider="github",
    remote_user="acme",
    remote_reponame="frontend",
    branch="main",
    commit_id="abc123",
):
    from Vire.objects.validation_models import ValidatorContext
    return ValidatorContext(
        job_uuid=job_uuid,
        user_uuid=user_uuid,
        provider=provider,
        remote_user=remote_user,
        remote_reponame=remote_reponame,
        branch=branch,
        commit_id=commit_id,
    )


def make_parsed_toml(
    framework="vite",
    package_manager="npm",
    framework_version="5.0",
    output_dir="dist",
    install_req=True,
):
    from Vire.objects.validation_models import ParsedTOMLObject
    return ParsedTOMLObject(
        framework=framework,
        package_manager=package_manager,
        framework_version=framework_version,
        output_dir=output_dir,
        install_req=install_req,
    )


# ─── schema_check tests ───────────────────────────────────────────────────────

class TestCheckTomlSchema:
    """check_toml_schema validates the structure of a parsed TOML dict."""

    @pytest.mark.asyncio
    async def test_valid_toml_dict_returns_parsed_object(self):
        from Vire.project_manifest.schema_check import check_toml_schema

        valid_dict = {
            "details": {
                "framework": "vite",
                "package_manager": "npm",
            },
            "project": {
                "output_dir": "dist",
                "framework_version": "5.0",
                "dependencies": True,
            },
        }

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await check_toml_schema(valid_dict)

        from Vire.objects.validation_models import ParsedTOMLObject
        assert isinstance(result, ParsedTOMLObject)
        assert result.framework == "vite"
        assert result.package_manager == "npm"
        assert result.output_dir == "dist"
        assert result.install_req is True

    @pytest.mark.asyncio
    async def test_missing_details_table_raises(self):
        from Vire.project_manifest.schema_check import check_toml_schema
        from shared.errors.validation_errors import InvalidVireTomlError

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await check_toml_schema({"project": {"output_dir": "dist"}})

    @pytest.mark.asyncio
    async def test_missing_project_table_raises(self):
        from Vire.project_manifest.schema_check import check_toml_schema
        from shared.errors.validation_errors import InvalidVireTomlError

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await check_toml_schema({"details": {"framework": "vite", "package_manager": "npm"}})

    @pytest.mark.asyncio
    async def test_missing_framework_raises(self):
        from Vire.project_manifest.schema_check import check_toml_schema
        from shared.errors.validation_errors import InvalidVireTomlError

        bad = {
            "details": {"package_manager": "npm"},  # no framework
            "project": {"output_dir": "dist", "framework_version": "5.0", "dependencies": True},
        }
        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await check_toml_schema(bad)

    @pytest.mark.asyncio
    async def test_missing_output_dir_raises(self):
        from Vire.project_manifest.schema_check import check_toml_schema
        from shared.errors.validation_errors import InvalidVireTomlError

        bad = {
            "details": {"framework": "vite", "package_manager": "npm"},
            "project": {"framework_version": "5.0", "dependencies": True},  # no output_dir
        }
        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await check_toml_schema(bad)


# ─── parse_toml tests ─────────────────────────────────────────────────────────

class TestParseToml:
    """parse_toml parses a TOML string into ParsedTOMLObject."""

    @pytest.mark.asyncio
    async def test_valid_toml_string_returns_object(self):
        from Vire.project_manifest.parse_toml import parse_toml

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await parse_toml(VALID_TOML)

        assert result.framework == "vite"
        assert result.package_manager == "npm"
        assert result.output_dir == "dist"
        assert result.install_req is True

    @pytest.mark.asyncio
    async def test_invalid_toml_syntax_raises_toml_decode_error(self):
        from Vire.project_manifest.parse_toml import parse_toml
        from tomllib import TOMLDecodeError

        with pytest.raises(TOMLDecodeError):
            await parse_toml(INVALID_TOML_SYNTAX)

    @pytest.mark.asyncio
    async def test_missing_details_table_raises_invalid_vire_toml(self):
        from Vire.project_manifest.parse_toml import parse_toml
        from shared.errors.validation_errors import InvalidVireTomlError

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await parse_toml(MISSING_DETAILS_TOML)

    @pytest.mark.asyncio
    async def test_missing_project_table_raises_invalid_vire_toml(self):
        from Vire.project_manifest.parse_toml import parse_toml
        from shared.errors.validation_errors import InvalidVireTomlError

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await parse_toml(MISSING_PROJECT_TOML)

    @pytest.mark.asyncio
    async def test_missing_required_field_raises_invalid_vire_toml(self):
        """package_manager is absent — schema check must raise."""
        from Vire.project_manifest.parse_toml import parse_toml
        from shared.errors.validation_errors import InvalidVireTomlError

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await parse_toml(MISSING_FIELD_TOML)


# ─── validator.validate_package_json tests ────────────────────────────────────

class TestValidatePackageJson:
    """validate_package_json rejects scripts with security-sensitive lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_clean_package_json_returns_true(self):
        from Vire.project_manifest.validator import validate_package_json

        result = await validate_package_json(CLEAN_PACKAGE_JSON)
        assert result is True

    @pytest.mark.asyncio
    async def test_postinstall_key_raises(self):
        from Vire.project_manifest.validator import validate_package_json
        from shared.errors.validation_errors import InvalidPackageJsonError

        with pytest.raises(InvalidPackageJsonError):
            await validate_package_json(BLOCKED_PACKAGE_JSON)

    @pytest.mark.asyncio
    async def test_start_key_raises(self):
        from Vire.project_manifest.validator import validate_package_json
        from shared.errors.validation_errors import InvalidPackageJsonError

        with pytest.raises(InvalidPackageJsonError):
            await validate_package_json(START_SCRIPT_PACKAGE_JSON)

    @pytest.mark.asyncio
    async def test_missing_scripts_section_is_safe(self):
        """package.json without 'scripts' key at all should pass."""
        from Vire.project_manifest.validator import validate_package_json

        no_scripts = '{"name": "my-app", "version": "1.0.0"}'
        result = await validate_package_json(no_scripts)
        assert result is True

    @pytest.mark.asyncio
    async def test_malformed_json_raises_invalid_package_json_error(self):
        from Vire.project_manifest.validator import validate_package_json
        from shared.errors.validation_errors import InvalidPackageJsonError

        with pytest.raises(InvalidPackageJsonError):
            await validate_package_json("{ this is not json")

    @pytest.mark.asyncio
    async def test_preinstall_key_raises(self):
        from Vire.project_manifest.validator import validate_package_json
        from shared.errors.validation_errors import InvalidPackageJsonError

        preinstall_json = '{"scripts": {"preinstall": "bad", "build": "vite build"}}'
        with pytest.raises(InvalidPackageJsonError):
            await validate_package_json(preinstall_json)


# ─── validator.validate_toml tests ───────────────────────────────────────────

class TestValidateToml:
    """validate_toml checks framework, lockfile/pm pairing, and output_dir regex."""

    @pytest.mark.asyncio
    async def test_valid_vite_npm_dist_passes(self):
        from Vire.project_manifest.validator import validate_toml

        # Should complete without raising
        await validate_toml(
            lockfile_name="package-lock.json",
            package_manager="npm",
            output_dir="dist",
            framework="vite",
        )

    @pytest.mark.asyncio
    async def test_unsupported_framework_raises(self):
        from Vire.project_manifest.validator import validate_toml
        from shared.errors.validation_errors import UnsupportedFrameworkError

        with pytest.raises(UnsupportedFrameworkError):
            await validate_toml(
                lockfile_name="package-lock.json",
                package_manager="npm",
                output_dir="dist",
                framework="rails",  # not in available_frameworks
            )

    @pytest.mark.asyncio
    async def test_lockfile_pm_mismatch_raises(self):
        """pnpm-lock.yaml does not match npm — should raise PackageManagerException."""
        from Vire.project_manifest.validator import validate_toml
        from shared.errors.validation_errors import PackageManagerException

        with pytest.raises(PackageManagerException):
            await validate_toml(
                lockfile_name="pnpm-lock.yaml",
                package_manager="npm",  # mismatch: pnpm lockfile but npm pm
                output_dir="dist",
                framework="vite",
            )

    @pytest.mark.asyncio
    async def test_output_dir_with_special_chars_raises(self):
        """output_dir containing '../' or spaces must fail the regex."""
        from Vire.project_manifest.validator import validate_toml
        from shared.errors.validation_errors import InvalidOutDirError

        for bad_dir in ("../etc", "dir with spaces", "dir;rm -rf", ""):
            if bad_dir == "":
                # empty string: re.fullmatch returns None
                with pytest.raises(InvalidOutDirError):
                    await validate_toml(
                        lockfile_name="package-lock.json",
                        package_manager="npm",
                        output_dir=bad_dir,
                        framework="vite",
                    )
            else:
                with pytest.raises(InvalidOutDirError):
                    await validate_toml(
                        lockfile_name="package-lock.json",
                        package_manager="npm",
                        output_dir=bad_dir,
                        framework="vite",
                    )

    @pytest.mark.asyncio
    async def test_output_dir_with_hyphens_and_underscores_passes(self):
        from Vire.project_manifest.validator import validate_toml

        # All alphanumeric + hyphens + underscores should pass
        await validate_toml(
            lockfile_name="package-lock.json",
            package_manager="npm",
            output_dir="my_build-output2",
            framework="vite",
        )

    @pytest.mark.asyncio
    async def test_no_lockfile_skips_pm_check(self):
        """When lockfile_name is None, the lockfile/pm match check is skipped."""
        from Vire.project_manifest.validator import validate_toml

        # Even with a mismatched or None lockfile, no error if lockfile_name is None
        await validate_toml(
            lockfile_name=None,
            package_manager="npm",
            output_dir="dist",
            framework="vite",
        )


# ─── parse_vire_toml integration tests ──────────────────────────────────

class TestFetchAndParseToml:
    """
    parse_vire_toml fetches vire.toml via HTTP then parses it.

    HTTP call is mocked; we verify the parsing pipeline is exercised end-to-end.
    """

    def _make_mock_response(self, content: str):
        """Create a mock httpx.Response-like object."""
        mock_resp = MagicMock()
        mock_resp.content = content.encode("utf-8")
        return mock_resp

    @pytest.mark.asyncio
    async def test_valid_toml_returns_parsed_toml_object(self):
        from Vire.core.validate.parse_vire_toml import parse_vire_toml
        from Vire.objects.validation_models import ParsedTOMLObject
        from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml

        vc = make_validator_context()
        mock_resp = self._make_mock_response(VALID_TOML)

        with patch(PATCH_REQUEST, new_callable=AsyncMock, return_value=mock_resp), \
             patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
             vire_toml_str = await fetch_vire_toml(
                 provider=vc.provider,
                 remote_user=vc.remote_user,
                 remote_reponame=vc.remote_reponame,
                 branch=vc.branch,
             )
             print(vire_toml_str)
             
             result = await parse_vire_toml(VC=vc, vire_toml_str=vire_toml_str)

        assert isinstance(result, ParsedTOMLObject)
        assert result.framework == "vite"

    @pytest.mark.asyncio
    async def test_invalid_toml_syntax_returns_none_and_dispatches_event(self):
        """
        When the fetched file is malformed TOML, parse_vire_toml catches
        InvalidTomlSyntaxError, dispatches an ErrorEvent, and returns None.
        """
        from Vire.core.validate.parse_vire_toml import parse_vire_toml
        from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml

        vc = make_validator_context()
        mock_resp = self._make_mock_response(INVALID_TOML_SYNTAX)

        with patch(PATCH_REQUEST, new_callable=AsyncMock, return_value=mock_resp), \
             patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
             vire_toml_str = await fetch_vire_toml(
                provider=vc.provider,
                remote_user=vc.remote_user,
                remote_reponame=vc.remote_reponame,
                branch=vc.branch,
             )

             result = await parse_vire_toml(VC=vc, vire_toml_str=vire_toml_str)
             print(mock_redis.await_count)

        # Returns None on validation failure
        assert result is None
        # An ErrorEvent with propagate_state=True was dispatched → redis called
        mock_redis.assert_called()

    @pytest.mark.asyncio
    async def test_missing_schema_returns_none(self):
        """Valid TOML syntax but missing [details] table → parse_vire_toml only catches
        InvalidTomlSyntaxError. InvalidVireTomlError (schema error) propagates up to the
        caller (validate_details), so it raises here."""
        from Vire.core.validate.parse_vire_toml import parse_vire_toml
        from shared.errors.validation_errors import InvalidVireTomlError

        vc = make_validator_context()

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
            with pytest.raises(InvalidVireTomlError):
                await parse_vire_toml(vc, vire_toml_str=MISSING_DETAILS_TOML)

    @pytest.mark.asyncio
    async def test_unsupported_provider_raises(self):
        """Unsupported git provider key error → UnsupportedGitProviderError → returns None."""
        from Vire.core.validate.parse_vire_toml import parse_vire_toml
        from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml
        from shared.errors.vire_errors import UnsupportedGitProviderError

        vc = make_validator_context(provider="bitbucket")  # not in PROVIDER_REGISTRY

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
                 with pytest.raises(UnsupportedGitProviderError):
                    vire_toml_str = await fetch_vire_toml(
                        provider=vc.provider,
                        remote_user=vc.remote_user,
                        remote_reponame=vc.remote_reponame,
                        branch=vc.branch,
                    )

# ─── validate_vire_toml integration tests ────────────────────────────────────

class TestValidateVireToml:
    """validate_vire_toml calls validate_toml and dispatches events on failure."""

    @pytest.mark.asyncio
    async def test_valid_toml_returns_true(self):
        from Vire.core.validate.validate_vire_toml import validate_vire_toml
        from Vire.objects.validation_models import TOMLValidationParams

        vc = make_validator_context()
        pto = make_parsed_toml()
        tvp = TOMLValidationParams(
            lockfile_name="package-lock.json",
            common_line="main from acme/frontend from Github",
            ts="01-01-2024",
        )

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await validate_vire_toml(TVP=tvp, VC=vc, PTO=pto)

        assert result is True

    @pytest.mark.asyncio
    async def test_unsupported_framework_returns_none_and_dispatches(self):
        from Vire.core.validate.validate_vire_toml import validate_vire_toml
        from Vire.objects.validation_models import TOMLValidationParams

        vc = make_validator_context()
        pto = make_parsed_toml(framework="unsupported-framework-xyz")
        tvp = TOMLValidationParams(
            lockfile_name="package-lock.json",
            common_line="main from acme/frontend",
            ts="01-01-2024",
        )

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_vire_toml(TVP=tvp, VC=vc, PTO=pto)

        assert result is None
        mock_redis.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_output_dir_returns_none_and_dispatches(self):
        from Vire.core.validate.validate_vire_toml import validate_vire_toml
        from Vire.objects.validation_models import TOMLValidationParams

        vc = make_validator_context()
        pto = make_parsed_toml(output_dir="../evil")
        tvp = TOMLValidationParams(
            lockfile_name="package-lock.json",
            common_line="main from acme/frontend",
            ts="01-01-2024",
        )

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_vire_toml(TVP=tvp, VC=vc, PTO=pto)

        assert result is None
        mock_redis.assert_called()


# ─── validate_lockfile integration tests ───────────────────────────

class TestFetchAndValidateLockfile:
    """
    validate_lockfile:
      - returns lockfile name when install_req=True and lockfile is found.
      - returns None (no fetch) when install_req=False.
      - raises/dispatches on unsupported PM.
    """

    def _make_lvp(self, install_req=True, pm="npm"):
        from Vire.objects.validation_models import LockfileValidationParams
        return LockfileValidationParams(
            install_req=install_req,
            commit_id="abc123sha",
            package_manager=pm,
            provider="github",
        )

    def _make_git_tree_response(self, lockfile_name: str, pm: str, size: int = 100):
        """Build a fake GitHub git tree API response containing the given lockfile."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "tree": [
                {"path": lockfile_name, "type": "blob", "size": size},
                {"path": "src/index.ts", "type": "blob", "size": 200},
            ]
        }
        return mock_resp

    @pytest.mark.asyncio
    async def test_install_req_false_returns_none_immediately(self):
        from Vire.core.validate.validate_lockfile import validate_lockfile
        from Vire.objects.validation_models import LockfileValidationParams

        lvp = LockfileValidationParams(
            install_req=False,
            commit_id="abc123",
            package_manager="npm",
            provider="github",
        )
        vc = make_validator_context()

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await validate_lockfile(LVP=lvp, VC=vc, lockfile_names=["package-lock.json"])

        # install_req=False → returns None without checking lockfile_names
        assert result is None

    @pytest.mark.asyncio
    async def test_unsupported_pm_dispatches_event_and_returns_none(self):
        from Vire.core.validate.validate_lockfile import validate_lockfile
        from Vire.objects.validation_models import LockfileValidationParams

        lvp = LockfileValidationParams(
            install_req=True,
            commit_id="abc123",
            package_manager="yarn3-berry",  # not in package_managers_list
            provider="github",
        )
        vc = make_validator_context()

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_lockfile(
                LVP=lvp, VC=vc, lockfile_names=["yarn.lock"]
            )

        assert result is None
        mock_redis.assert_called()

    @pytest.mark.asyncio
    async def test_valid_npm_lockfile_found_returns_filename(self):
        from Vire.core.validate.validate_lockfile import validate_lockfile

        lvp = self._make_lvp(install_req=True, pm="npm")
        vc = make_validator_context()
        mock_resp = self._make_git_tree_response("package-lock.json", "npm")

        # validate_lockfile no longer fetches; lockfile_names comes from the caller
        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await validate_lockfile(
                LVP=lvp, VC=vc, lockfile_names=["package-lock.json", "src/index.ts"]
            )
        assert result == "package-lock.json"

    @pytest.mark.asyncio
    async def test_valid_pnpm_lockfile_found_returns_filename(self):
        from Vire.core.validate.validate_lockfile import validate_lockfile

        lvp = self._make_lvp(install_req=True, pm="pnpm")
        vc = make_validator_context()
        mock_resp = self._make_git_tree_response("pnpm-lock.yaml", "pnpm")

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await validate_lockfile(
                LVP=lvp, VC=vc, lockfile_names=["pnpm-lock.yaml", "src/index.ts"]
            )

        assert result == "pnpm-lock.yaml"

    @pytest.mark.asyncio
    async def test_no_lockfile_in_tree_dispatches_and_returns_none(self):
        """When no matching lockfile exists in the names list, PackageManagerException is
        raised internally and caught → dispatches event and returns None."""
        from Vire.core.validate.validate_lockfile import validate_lockfile

        lvp = self._make_lvp(install_req=True, pm="npm")
        vc = make_validator_context()

        # Names list contains no lockfile matching npm's expected 'package-lock.json'
        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_lockfile(
                LVP=lvp, VC=vc, lockfile_names=["src/index.ts", "README.md"]
            )

        assert result is None
        mock_redis.assert_called()


# ─── validate_pkgjson integration tests ────────────────────────────

class TestFetchAndValidatePkgjson:
    """validate_pkgjson fetches package.json and validates it."""

    def _make_pjvp(self, lockfile_name="package-lock.json"):
        from Vire.objects.validation_models import PkgJSONValidationParams
        return PkgJSONValidationParams(
            lockfile_name=lockfile_name,
            common_line="main from acme/frontend",
            ts="01-01-2024",
        )

    def _make_mock_response(self, text: str, status: int = 200):
        resp = MagicMock()
        resp.text = text
        resp.content = text.encode("utf-8")
        resp.status_code = status
        return resp

    @pytest.mark.asyncio
    async def test_clean_package_json_returns_true(self):
        from Vire.core.validate.resolve_packagejson import validate_pkgjson

        vc = make_validator_context()

        # validate_pkgjson no longer fetches; package_json_str is passed directly
        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock):
            result = await validate_pkgjson(VC=vc, package_json_str=CLEAN_PACKAGE_JSON)

        assert result is True

    @pytest.mark.asyncio
    async def test_blocked_script_in_package_json_returns_false_and_dispatches(self):
        from Vire.core.validate.resolve_packagejson import validate_pkgjson

        vc = make_validator_context()

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_pkgjson(VC=vc, package_json_str=BLOCKED_PACKAGE_JSON)

        # Returns False when a blocked script key is detected; event is dispatched
        assert result is False
        mock_redis.assert_called()

    @pytest.mark.asyncio
    async def test_start_script_in_package_json_returns_false_and_dispatches(self):
        """'start' is a blocked script key → validation fails → returns False and dispatches.
        This test replaces the former 'unsupported_provider' test; provider lookup was
        removed from validate_pkgjson in the refactor."""
        from Vire.core.validate.resolve_packagejson import validate_pkgjson

        vc = make_validator_context()

        with patch(PATCH_LOGGER), \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            result = await validate_pkgjson(VC=vc, package_json_str=START_SCRIPT_PACKAGE_JSON)

        assert result is False
        mock_redis.assert_called()


# ─── git provider adapter tests ───────────────────────────────────────────────

class TestGitProviderAdapter:
    """GithubAdapter constructs correct URLs for raw files and git trees."""

    def test_github_raw_url_format(self):
        from Vire.objects.git_provider_adapter import GithubAdapter

        adapter = GithubAdapter()
        url = adapter.get_raw_url(
            user="acme",
            repo_name="frontend",
            branch="main",
            path_name=".vire/vire.toml"
        )
        assert url == "https://raw.githubusercontent.com/acme/frontend/main/.vire/vire.toml"

    def test_github_clone_link_format(self):
        from Vire.objects.git_provider_adapter import GithubAdapter

        adapter = GithubAdapter()
        link = adapter.return_clone_link("acme", "frontend")
        assert link == "https://github.com/acme/frontend.git"

    def test_github_list_tree_url_format(self):
        from Vire.objects.git_provider_adapter import GithubAdapter

        adapter = GithubAdapter()
        url = adapter.return_list_tree("acme", "frontend", "abc123sha")
        assert url == "https://api.github.com/repos/acme/frontend/git/trees/abc123sha"

    def test_unsupported_provider_raises_key_error(self):
        from Vire.objects.git_provider_adapter import PROVIDER_REGISTRY

        with pytest.raises(KeyError):
            _ = PROVIDER_REGISTRY["gitlab"]()

    def test_github_is_in_provider_registry(self):
        from Vire.objects.git_provider_adapter import PROVIDER_REGISTRY, GithubAdapter

        assert "github" in PROVIDER_REGISTRY
        assert isinstance(PROVIDER_REGISTRY["github"](), GithubAdapter)
