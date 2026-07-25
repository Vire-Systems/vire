"""
This module (cli_parser) handles cli arg parsing.

Functions -

1. load_parser (sync)
"""

import argparse
import json
from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from shared.errors.worker_errors import CredentialError


def load_parser():
    """argparse terminal argument parser."""
    parser = argparse.ArgumentParser(
        description="An isolated,individual worker process handling builds."
    )

    _ = parser.add_argument(
        "--json_struct",
        type=str,
        required=True,
        help="""
        JSON structure containing 
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
    json_struct = json.loads(args.json_struct)

    # Variables updation.
    try:
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
        return state
    except KeyError as exc:
        raise CredentialError from exc
