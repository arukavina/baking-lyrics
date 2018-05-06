#!/usr/bin/env bash

source ~/python-venv/baking-lyrics/bin/activate
export FLASK_APP=baking_api
export FLASK_ENV=development
export APP_CONFIG_FILE=/Users/arukavina/GitHub/Baking-Lyrics/config/development.py
flask run