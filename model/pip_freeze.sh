#!/usr/bin/env bash

echo "Activating python venv: [model-ml]."
source ~/python-venv/ml-model/bin/activate
echo "Freezing pip (as is) now."
pip freeze > requirements.txt