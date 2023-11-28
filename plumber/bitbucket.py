import json
from json import JSONDecodeError
import logging
import os
import requests


def commit_changes(repo_slug: str, message: str, pipelines_config: str, file_extension: str = "yaml", files_field: list = None, branch: str = "main") -> None:
    """
    Commit and push changes made to a remote branch

    :param repo_slug: the name of a repository
    :param message: a description for the commit
    :param pipelines_config: the contents of a pipelines file
    :param file_extension: the file extension used by the bitbucket-pipelines file
    :param files_field: a list of files fields for the commit
    :param branch: the name of a branch to commit a change to
    """
    url = f"https://api.bitbucket.org/2.0/repositories/signiant/{repo_slug}/src"
    auth = get_bitbucket_credentials()
    headers = {
        "Accept": "application/json"
    }
    # The Bitbucket API documentation is god awful
    if files_field:
        files = files_field
    else:
        files = []
    files.extend(
        [
            (f"bitbucket-pipelines.{file_extension}", f"{pipelines_config}"),
            ("message", (None, message)),
            ("branch", (None, f"{branch}"))
        ]
    )

    requests.request(
        "POST",
        url,
        auth=auth,
        headers=headers,
        files=files
    )


def create_branch(repo_slug: str, step: str) -> str | None:
    """
    Create a branch in a repository

    :param repo_slug: the name of a repository
    :param step: the name of a Bitbucket pipeline build step
    :return: the name of the new branch
    """
    url = f"https://api.bitbucket.org/2.0/repositories/signiant/{repo_slug}/refs/branches"
    auth = get_bitbucket_credentials()
    headers = {
        "Accept": "application/json"
    }
    payload = {
        "name": f"remove-{step}",
        "target": {
            "hash": f"remove-{step}",
        }
    }

    response = requests.request(
        "POST",
        url,
        auth=auth,
        headers=headers,
        json=payload
    )

    try:
        if "error" in json.loads(response.text):
            logging.error(
                f"Failed to create branch for {repo_slug}: " +
                json.loads(response.text)["error"]["message"]
            )
            return

        branch = json.loads(response.text).get('name')
    except JSONDecodeError:
        logging.error(f"Failed to create branch for {repo_slug}: " + response.reason)
        return

    return branch


def create_pull_request(repo_slug: str, branch: str, step: str, reviewers: list) -> None:
    """
    Create a pull request for a branch

    :param repo_slug: the name of a repository
    :param branch: the name of a branch to use as the source for the pull request
    :param step: a step that was removed
    :param reviewers: the UUIDs of the various reviewers
    """
    url = f"https://api.bitbucket.org/2.0/repositories/signiant/{repo_slug}/pullrequests"
    auth = get_bitbucket_credentials()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "title": f"Remove {step} from pipelines",
        "source": {
            "branch": {
                "name": branch
            }
        },
        "reviewers": reviewers
    }

    response = requests.request(
        "POST",
        url,
        auth=auth,
        headers=headers,
        json=payload
    )

    try:
        if "error" in json.loads(response.text):
            logging.error(
                f"Failed to create pull request for {repo_slug}: " +
                json.loads(response.text)["error"]["message"]
            )
            return

        branch = json.loads(response.text).get('name')
    except JSONDecodeError:
        logging.error(f"Failed to create pull request for {repo_slug}: " + response.reason)
        return

    return branch


def get_bitbucket_credentials() -> tuple:
    """
    Get Bitbucket credentials from environment

    :return: Bitbucket credentials
    """
    return os.getenv('BB_USER_ID'), os.getenv('BB_APP_PASS')


def get_latest_commit_hash(repo_slug: str, branch: str = "main") -> str | None:
    """
    Get the hash of the latest commit

    :param repo_slug: the name of a repository
    :param branch: the name of the branch to get the commit hash from
    :return: the hash of the most recent commit
    """
    url = f"https://api.bitbucket.org/2.0/repositories/signiant/{repo_slug}/commits"
    auth = get_bitbucket_credentials()
    headers = {
        "Accept": "application/json"
    }
    params = {
        "include": branch
    }

    response = requests.request(
        "GET",
        url,
        auth=auth,
        headers=headers,
        params=params
    )

    try:
        if "error" in json.loads(response.text):
            logging.error(
                f"Failed to latest commit hash for {repo_slug}: " +
                json.loads(response.text)["error"]["message"]
            )
            return

        commit_hash = json.loads(response.text).get("values")[0].get("hash")
    except JSONDecodeError:
        logging.error(f"Failed to get latest commit hash for {repo_slug} on {branch}: " + response.reason)
        return

    return commit_hash


def get_pipelines_bytes(repo_slug: str, commit: str, extension: str) -> bytes | None:
    """
    Get the pipelines file in a repository

    :param repo_slug: the name of a repository
    :param commit: the hash of the most recent commit
    :param extension: the file extension used for the pipelines file
    :return: a bytes representation of a repo's pipelines file
    """
    url = (
        f"https://api.bitbucket.org/2.0/repositories/signiant/"
        f"{repo_slug}/src/{commit}/bitbucket-pipelines.{extension}"
    )
    auth = get_bitbucket_credentials()
    headers = {
        "Accept": "application/json"
    }

    response = requests.request(
        "GET",
        url,
        auth=auth,
        headers=headers
    )

    if response.status_code != 200:
        logging.error(f"Failed to get bitbucket-pipelines.{extension} for {repo_slug}: " + response.reason)
        return

    pipelines_config = response.content
    return pipelines_config
