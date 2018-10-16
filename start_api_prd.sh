#!/usr/bin/env bash

cd /var/www/bakinglyrics
export PYTHONPATH=$PWD
python baking/refresh_database.py
source /opt/python/venv/bakinglyrics/bin/activate
waitress-serve --call 'baking.main:create_app'