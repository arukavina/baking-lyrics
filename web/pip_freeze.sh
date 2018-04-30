#!/usr/bin/env bash

echo "Activating python venv [bl-web]."
source ~/python-venv/bl-web/bin/activate
echo "Freezing pip (as is) now."
pip freeze > requirements.txt