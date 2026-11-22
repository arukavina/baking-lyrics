"""
Build info resolution (baking.main.util.build_info) and the /api/v1/general/version endpoint.
"""

# Generic
import subprocess
import tomllib

# Libs
import pytest

# Own
from baking.main import REPO_ROOT
from baking.main.util import build_info

SHA = '0123456789abcdef0123456789abcdef01234567'
DATE = '2026-11-22T10:00:00+01:00'


def _project_version():
    with open(REPO_ROOT / 'pyproject.toml', 'rb') as fh:
        return tomllib.load(fh)['project']['version']


@pytest.fixture(autouse=True)
def _no_commit_env(monkeypatch):
    """The developer machine (or CI) must not leak build env vars into these tests."""
    monkeypatch.delenv(build_info.COMMIT_SHA_ENV, raising=False)
    monkeypatch.delenv(build_info.COMMIT_DATE_ENV, raising=False)


@pytest.fixture
def fake_git(monkeypatch):
    """Replaces subprocess.run in build_info with a fake git; returns the list of recorded calls."""
    calls = []

    def _run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd[1:] == ['rev-parse', 'HEAD']:
            stdout = SHA + '\n'
        elif cmd[1:] == ['log', '-1', '--format=%cI']:
            stdout = DATE + '\n'
        else:
            raise AssertionError(f'unexpected command {cmd}')
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr='')

    monkeypatch.setattr(build_info.subprocess, 'run', _run)
    return calls


@pytest.fixture
def no_git(monkeypatch):
    def _run(cmd, **kwargs):
        raise FileNotFoundError('git')

    monkeypatch.setattr(build_info.subprocess, 'run', _run)


def test_env_vars_win_over_git(monkeypatch, fake_git):
    monkeypatch.setenv(build_info.COMMIT_SHA_ENV, SHA)
    monkeypatch.setenv(build_info.COMMIT_DATE_ENV, DATE)

    info = build_info.resolve_build_info(REPO_ROOT)

    assert info == {'version': _project_version(), 'commit': SHA, 'date': DATE}
    assert fake_git == []


def test_git_is_queried_from_repo_root(fake_git):
    info = build_info.resolve_build_info(REPO_ROOT)

    assert info == {'version': _project_version(), 'commit': SHA, 'date': DATE}
    assert [cmd for cmd, _ in fake_git] == [['git', 'rev-parse', 'HEAD'], ['git', 'log', '-1', '--format=%cI']]
    for _, kwargs in fake_git:
        assert kwargs['cwd'] == str(REPO_ROOT)
        assert kwargs['timeout'] == build_info.GIT_TIMEOUT_SECONDS


@pytest.mark.parametrize('error', [FileNotFoundError('git'),
                                   subprocess.TimeoutExpired('git', 2),
                                   subprocess.CalledProcessError(128, 'git')])
def test_null_when_git_is_unavailable(monkeypatch, error):
    def _run(cmd, **kwargs):
        raise error

    monkeypatch.setattr(build_info.subprocess, 'run', _run)

    info = build_info.resolve_build_info(REPO_ROOT)

    assert info == {'version': _project_version(), 'commit': None, 'date': None}


def test_version_is_null_without_pyproject(tmp_path, no_git):
    assert build_info.resolve_build_info(tmp_path) == {'version': None, 'commit': None, 'date': None}


def test_version_endpoint_shape(client):
    response = client.get('/api/v1/general/version')

    assert response.status_code == 200
    assert set(response.json) == {'version', 'commit', 'date'}
    assert response.json['version'] == _project_version()


def test_version_endpoint_uses_env_override(monkeypatch, make_app):
    monkeypatch.setenv(build_info.COMMIT_SHA_ENV, SHA)
    monkeypatch.setenv(build_info.COMMIT_DATE_ENV, DATE)

    app = make_app()
    response = app.test_client().get('/api/v1/general/version')

    assert app.config['BUILD_COMMIT'] == SHA
    assert response.status_code == 200
    assert response.json == {'version': _project_version(), 'commit': SHA, 'date': DATE}


def test_version_endpoint_nulls_without_git(make_app, no_git):
    app = make_app()
    response = app.test_client().get('/api/v1/general/version')

    assert response.status_code == 200
    assert response.json == {'version': _project_version(), 'commit': None, 'date': None}
