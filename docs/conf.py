"""Sphinx configuration of the Baking Lyrics model documentation (built on Read the Docs, see .readthedocs.yaml)."""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

project = 'Baking Lyrics model'
author = 'Andrei Rukavina'
copyright = '2018 to 2026, Andrei Rukavina'
release = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
version = release

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

source_suffix = {'.md': 'markdown'}
root_doc = 'index'
exclude_patterns = ['_build']
language = 'en'
# The docstrings use Markdown style `code`; render single backticks as code, not italics
default_role = 'code'

# Training and export need torch and onnx, which the docs build does not install; the reference pages only read
# docstrings and signatures, so these imports are mocked.
autodoc_mock_imports = ['torch', 'onnx', 'onnxruntime', 'fast_langdetect', 'kagglehub']
autodoc_default_options = {'members': True, 'member-order': 'bysource'}
autodoc_typehints = 'description'

myst_enable_extensions = ['colon_fence', 'deflist']
myst_heading_anchors = 3

html_theme = 'furo'
html_title = f'Baking Lyrics model {release}'
html_theme_options = {
    'source_repository': 'https://github.com/arukavina/baking-lyrics/',
    'source_branch': 'master',
    'source_directory': 'docs/',
}


def _link_included_readme(app, relative_path, parent_docname, content):
    """ml/README.md links BUNDLE.md for GitHub; on this site that page is bundle.md (Linux paths are case sensitive)."""
    if relative_path.name == 'README.md':
        content[0] = content[0].replace('](BUNDLE.md)', '](bundle.md)')


def setup(app):
    app.connect('include-read', _link_included_readme)
