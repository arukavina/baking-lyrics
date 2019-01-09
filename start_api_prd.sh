#!/usr/bin/env bash

cd /var/www/bakinglyrics
export PYTHONPATH=$PWD
export APP_CONFIG_FILE=config/production.py
source /opt/python/venv/bakinglyrics/bin/activate
python baking/refresh_database.py
waitress-serve --call 'baking.main:create_app'