import argparse
import os

import bitbucket as bb
import json
import logging
import sys

logging.basicConfig(format="%(asctime)s - %(levelname)8s: %(message)s", stream=sys.stdout)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def get_indentation(pipelines_config: str, start: int):
    """
    Retrieve the level of indentation of a step

    :param pipelines_config: the contents of a pipelines file
    :param start: the start index in the pipelines content
    :return: the number of spaces used for indentation
    """
    num_spaces = 0
    for i in range(start - 1, 0, -1):
        if pipelines_config[i] != "\n" and pipelines_config[i] != " " and pipelines_config[i] != "#":
            break
        num_spaces += 1
    return num_spaces


def find_next_section(pipelines_config: str, start: int, keys: tuple) -> int:
    """
    Find the index of the next occurring section in a pipelines file

    :param pipelines_config: the contents of a pipelines file
    :param start: the start index in the pipelines content
    :param keys: a list of keys to search for
    :return: the index of the first occurrence of the next section
    """
    sections = []

    for key in keys:
        index = pipelines_config.find(key, start)
        if index != -1:
            sections.append(index)

    return min(sections)


def delete_section(pipelines_config: str, section: str) -> str | None:
    """
    Remove the first occurrence of a section from a repository's pipelines file.

    :param pipelines_config: the contents of a pipelines file
    :param section: the section to be deleted
    :return: the pipelines config with the specified section removed
    """
    try:
        start = pipelines_config.index(f"- step: {section}")
        end = find_next_section(
            pipelines_config,
            start + 7,
            ("- step:", "pipelines:", "branches")
        )

        # Adjust start and end indexes to account for indentation
        start -= get_indentation(pipelines_config, start)
        end -= get_indentation(pipelines_config, end)

        pipelines_config = pipelines_config[:start] + pipelines_config[end:]
    except ValueError:
        return

    return pipelines_config


def delete_steps(pipelines_config: str, step: str) -> str | None:
    """
    Delete pipeline build step anchors and aliases from pipelines file content.

    :param pipelines_config: the contents of a pipelines file
    :param step: the name of the step to be deleted
    :return: the updated pipelines config with the specified step's anchors/aliases removed
    """
    # Delete anchors
    pipelines_config = delete_section(pipelines_config, f"&{step}")

    if not pipelines_config:
        return

    # Delete aliases
    while pipelines_config.find(f"- step: *{step}") != -1:
        pipelines_config = delete_section(pipelines_config, f"*{step}")

    return pipelines_config


def clean_pipelines(repositories: list, step: str, files_field: list, reviewers: list, dry_run: bool) -> None:
    """
    Remove a build step from the pipelines file of Bitbucket repositories

    :param repositories: Bitbucket repositories containing pipelines with obsolete build steps
    :param step: the name of the step to be deleted
    :param files_field: a list of files fields for the commit
    :param reviewers: the UUIDs of the various reviewers
    :param dry_run: a flag that determines if changes should be made
    """
    for repo_slug in repositories:
        logging.info(f"Beginning removal of {step} from {repo_slug} pipelines...")

        # Get the latest commit hash on the default branch
        logging.debug(f"Getting latest commit hash on main branch for {repo_slug}")
        commit = bb.get_latest_commit_hash(repo_slug, "main")
        if not commit:
            logging.info("Trying master...")
            commit = bb.get_latest_commit_hash(repo_slug, "master")
            if not commit:
                logging.error(f"No commits found on default branch in {repo_slug}. Skipping...")
                continue

        # Get contents of the repository's pipelines file
        logging.debug(f"Getting pipelines file for {repo_slug}...")
        extension = "yaml"
        pipelines_bytes = bb.get_pipelines_bytes(repo_slug, commit, extension)
        if not pipelines_bytes:
            logging.info("Trying bitbucket-pipelines.yml...")
            extension = "yml"
            pipelines_bytes = bb.get_pipelines_bytes(repo_slug, commit, extension)
            if not pipelines_bytes:
                logging.error(f"Could not retrieve bitbucket-pipelines file in {repo_slug}. Skipping...")
                continue

        pipelines_config = pipelines_bytes.decode("utf-8")

        logging.debug(f"Deleting {step} from {repo_slug} pipelines...")
        pipelines_config = delete_steps(pipelines_config, step)

        if not pipelines_config:
            logging.warning(f"Step not found in pipelines for repo {repo_slug}. Skipping...")
            continue

        # Commit changes and create a pull request
        if not dry_run:
            logging.debug(f"Committing changes for repo {repo_slug}...")
            bb.commit_changes(
                repo_slug,
                f"Remove {step} from bitbucket-pipelines.yaml",
                pipelines_config,
                extension,
                files_field,
                f"remove-{step}"
            )

            logging.debug(f"Creating pull request for branch remove-{step}...")
            bb.create_pull_request(repo_slug, f"remove-{step}", step, reviewers)


def main(config_file: str, dry_run: bool, verbose: bool) -> None:
    """
    The application entry-point

    :param config_file: a path to the plumber configuration file
    :param dry_run: a flag that determines if changes should be made
    :param verbose: a flag that determines the amount of logging messages
    """
    if not os.getenv("BB_USER_ID"):
        logging.error("Environment variable BB_USER_ID not set. Stopping...")
        sys.exit(1)

    if not os.getenv("BB_APP_PASS"):
        logging.error("Environment variable BB_APP_PASS not set. Stopping...")
        sys.exit(1)

    # Configure root logger level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    logging.info("Loading config...")
    with open(f"{config_file}", "r") as file:
        config = json.load(file)
        repositories = config["repositories"]
        steps = config["steps"]
        reviewers = config["reviewers"]

    # Remove steps from pipelines
    for step in steps:
        step_name = step["name"]
        form_fields = []
        for file in step["files"]:
            form_fields.append(("files", (None, file)))

        logging.info(f"Removing {step_name} from pipelines...")
        clean_pipelines(repositories, step_name, form_fields, reviewers, dry_run)
        logging.info(f"{step_name} removed from pipelines.")

    logging.info("Pipeline step deletion complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Bitbucket pipeline build step deletion tool")

    parser.add_argument(
        "-c", "--config",
        help="A path to the json-formatted configuration file.",
        dest="config",
        default="config.json"
    )
    parser.add_argument(
        "-d", "--dry-run",
        help="Run script in dry run mode, posting no messages to Slack.",
        dest="dry_run",
        action='store_true'
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Run script in verbose mode, outputting more info in the logs.",
        dest="verbose",
        action='store_true'
    )

    args = parser.parse_args()
    main(args.config, args.dry_run, args.verbose)
