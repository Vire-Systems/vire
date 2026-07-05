"""
This module (cli_parser) handles cli arg parsing.

Functions -

1. load_parser (sync)
"""

import argparse
import json

import utils.state as state

from schema.errors import CredentialError


def load_parser():
    """argparse terminal argument parser."""
    parser = argparse.ArgumentParser(description="An isolated,individual worker process handling builds.")

    parser.add_argument(
        "--json_struct",
        type=str,
        required=True,
        help="""
        JSON structure containing state.
        Example: '{
            "job_uuid":"<job_uuid>",
            "user_uuid":"<user_uuid>",
            "remote":"https://github.com/user/repo_name",
            "repo_name":"<name>"
            "framework":"<framework>",
            "pm":"<package manager>",
            "output_dir":"<dir>"
            "install_req":"<Bool>",
            "commit_id":"<sha256> str"
        }'""",
    )
    args = parser.parse_args()
    json_struct: dict = json.loads(args.json_struct)

    # Variables updation.
    try:
        state.job_uuid = json_struct["job_uuid"]
        state.user_uuid = json_struct["user_uuid"]
        state.remote = json_struct["remote"]
        state.repo_name = json_struct["repo_name"]
        state.framework = json_struct["framework"]
        state.package_manager = json_struct["pm"]
        state.install_req = json_struct["install_req"]
        state.OUTPUT_DIR = json_struct["output_dir"]
        state.COMMIT_ID = json_struct["commit_id"]

        if (state.job_uuid is None) or (state.user_uuid is None):
            raise CredentialError(
                f"Credential error. {'job_uuid' if state.job_uuid else 'user_uuid'} cannot be 'None'."
            )

        if (state.framework is None) or (state.package_manager is None):
            raise CredentialError(
                f"Credential error. {'framework' if state.framework else 'package_manager'} cannot be 'None'."
            )

        if (state.remote is None) or (state.repo_name is None):
            raise CredentialError(f"Credential error. {'Remote' if state.remote else 'repo_name'} cannot be 'None'.")

    except KeyError as exc:
        raise KeyError from exc
