#!/usr/bin/env python

import datetime

# Own
from flask import Flask
from baking_api.util import log_utils
app = Flask(__name__,
            instance_relative_config=True,
            static_folder="static/dist",
            template_folder="static")

# Load the default configuration
app.config.from_object('config.default')

# Load the configuration from the instance folder
app.config.from_pyfile('config.py')

# Load the file specified by the APP_CONFIG_FILE environment variable
# Variables defined here will override those in the default configuration
app.config.from_envvar('APP_CONFIG_FILE')

TS = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

log_utils.setup_logging('baking_api', TS, app.config)
logger = log_utils.get_logger('baking_api')

log_utils.print_imports_versions(logger)

logger.info('Initializing Flask Deamon...')

import baking_api.views
