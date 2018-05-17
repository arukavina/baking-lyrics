#!/usr/bin/env bash

echo "Activating python venv: [baking-lyrics]."
source ~/python-venv/baking-lyrics/bin/activate
echo "Freezing pip (as is) now."
pip freeze > requirements/prd.txt