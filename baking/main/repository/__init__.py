"""
Data access layer. The app holds one repository in ``app.extensions['repository']`` (see create_app);
code running in a request or app context gets it with get_repository().
"""

# Libs
from flask import current_app

# Own
from baking.main.repository.base import Repository
from baking.main.repository.dynamodb import DynamoRepository

EXTENSION_KEY = 'repository'


def repository_from_config(config):
    """
    Builds the DynamoDB repository from a Flask config.
    :param config: mapping with BAKING_TABLE_PREFIX, AWS_REGION, DYNAMODB_ENDPOINT_URL, CATALOG_CACHE_SECONDS
    :return: DynamoRepository
    """
    return DynamoRepository(prefix=config['BAKING_TABLE_PREFIX'],
                            region=config['AWS_REGION'],
                            endpoint_url=config.get('DYNAMODB_ENDPOINT_URL') or None,
                            cache_seconds=config.get('CATALOG_CACHE_SECONDS', 60))


def get_repository():
    """The repository of the current app."""
    return current_app.extensions[EXTENSION_KEY]


__all__ = ['EXTENSION_KEY', 'DynamoRepository', 'Repository', 'get_repository', 'repository_from_config']
