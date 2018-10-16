#!/usr/bin/env bash

cd /opt/python/bundle/2/app/baking-lyrics-master
source /opt/python/venv/bakinglyrics/bin/activate
waitress-serve --call 'api:create_app'