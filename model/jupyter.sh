#!/usr/bin/env bash


echo "Activating python venv: [model-ml]."
source ~/python-venv/ml-model/bin/activate

ipython kernel install --user --name=baking-lyrics

jupyer notebook