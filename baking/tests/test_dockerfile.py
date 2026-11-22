"""
The image only receives the paths the Dockerfile copies by name, so the build context needs no list of local
tool folders in .dockerignore.
"""

# Generic
import re

# Own
from baking.main import REPO_ROOT

ALLOWED_SOURCES = {'pyproject.toml', 'uv.lock', 'config', 'baking', 'ml'}


def copy_sources():
    """Sources of every COPY of the build context (COPY --from=<stage> copies from another image)."""
    sources = []
    for line in (REPO_ROOT / 'Dockerfile').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^\s*(?:COPY|ADD)\s+(.*)$', line, re.IGNORECASE)
        if match is None or '--from=' in match.group(1):
            continue
        parts = [part for part in match.group(1).split() if not part.startswith('--')]
        sources.extend(parts[:-1])
    return sources


def test_dockerfile_copies_explicit_paths_only():
    sources = copy_sources()

    assert sources
    assert set(sources) <= ALLOWED_SOURCES
    assert not {'.', './', '*'} & set(sources)


def test_ml_is_restricted_to_the_serving_modules():
    lines = (REPO_ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()

    assert 'ml/*' in lines
    assert {line for line in lines if line.startswith('!ml/')} == {'!ml/__init__.py', '!ml/generate.py',
                                                                   '!ml/tokenizer.py'}
