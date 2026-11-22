"""
Build information (version, commit and commit date) reported by the general version endpoint.
"""

# Generic
import logging
import os
import subprocess
import tomllib
from pathlib import Path

logger = logging.getLogger('baking-api')

COMMIT_SHA_ENV = 'BAKING_COMMIT_SHA'
COMMIT_DATE_ENV = 'BAKING_COMMIT_DATE'
GIT_TIMEOUT_SECONDS = 2


def read_version(repo_root):
    """
    Reads the project version from pyproject.toml.
    :param repo_root: Path of the repository root
    :return: str or None when the file is missing or unreadable
    """
    try:
        with open(Path(repo_root) / 'pyproject.toml', 'rb') as fh:
            return tomllib.load(fh)['project']['version']
    except Exception:  # build info must never prevent the API from booting
        logger.debug('Could not read the version from pyproject.toml', exc_info=True)
        return None


def _run_git(repo_root, *args):
    """
    Runs a git command in repo_root and returns its stripped stdout, or None on any failure.
    """
    try:
        result = subprocess.run(['git', *args], cwd=str(repo_root), capture_output=True, text=True,
                                timeout=GIT_TIMEOUT_SECONDS, check=True)
    except Exception:  # git missing, not a repository, timeout...
        logger.debug('git %s failed', ' '.join(args), exc_info=True)
        return None
    return result.stdout.strip() or None


def resolve_build_info(repo_root):
    """
    Resolves the build version, commit sha and commit date (ISO 8601).

    The BAKING_COMMIT_SHA / BAKING_COMMIT_DATE environment variables win (deploys without .git): when
    either is set, git is not queried so sha and date never come from different sources. Otherwise git
    is queried. Any value that cannot be resolved is None.
    :param repo_root: Path of the repository root
    :return: dict with keys version, commit and date
    """
    commit = os.getenv(COMMIT_SHA_ENV) or None
    date = os.getenv(COMMIT_DATE_ENV) or None
    if commit is None and date is None:
        commit = _run_git(repo_root, 'rev-parse', 'HEAD')
        date = _run_git(repo_root, 'log', '-1', '--format=%cI')
    return {'version': read_version(repo_root), 'commit': commit, 'date': date}
