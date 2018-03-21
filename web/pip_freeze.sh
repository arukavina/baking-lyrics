#!/usr/bin/env bash

echo "Activating python venv: [bl-web]."
source ~/venv/bl-web/bin/activate
echo "Freezing pip (as is) now."
pip freeze > requirements.txt