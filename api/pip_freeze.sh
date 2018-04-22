#!/usr/bin/env bash

echo "Activating python venv: [bl-api]."
source ~/python-venv/bl-api/bin/activate
echo "Freezing pip (as is) now."
pip freeze > requirements.txt