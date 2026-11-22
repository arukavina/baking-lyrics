#!/usr/bin/env python

# Generic
import os
import tempfile

# Libs
import boto3.session
import pandas as pd
from botocore import exceptions
from flask import current_app as app

# Own
from baking.main.util import log_utils

logger = log_utils.get_logger('baking-api')


def get_bucket():
    """
    Lazily creates the boto3 S3 resource and returns the configured bucket.
    Must be called inside a Flask application context (reads AWS_REGION / AWS_BUCKET from current_app.config).
    """
    logger.info('Logging to AWS and accessing [s3] resource')
    s3 = boto3.session.Session().resource('s3', region_name=app.config['AWS_REGION'])

    logger.info('Connecting to AWS bucket: {}'.format(app.config['AWS_BUCKET']))
    return s3.Bucket(app.config['AWS_BUCKET'])


def read_bucket_object(object_name):
    """
    Reads S3 Bucket object
    :param object_name: Object path.
    :return: s3_object a tmp
    """

    return get_bucket().Object(object_name)


def _download_to_tmpfile(object_name):
    """
    Downloads an S3 object to a named temporary file and returns its path.
    The file is created with delete=False so it can be reopened on Windows; callers must remove it.
    """
    if object_name is None:
        raise AttributeError('object_name argument can not be None.')

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile(delete=False)

    try:
        with tmp as f:
            s3_object.download_fileobj(f)
    except exceptions.ClientError as e:
        os.remove(tmp.name)
        logger.debug(e.response)
        if e.response['Error']['Code'] == '404':
            logger.error(f'File does not exist: {object_name}')
        else:
            logger.error(f'Unexpected error: {e}')
            raise RuntimeError(e) from e
        raise FileNotFoundError(e) from e
    except Exception:
        os.remove(tmp.name)
        raise

    return tmp.name


def read_s3_csv_as_tmpfile(object_name=None):

    tmp_name = _download_to_tmpfile(object_name)
    try:
        return pd.read_csv(tmp_name)
    finally:
        os.remove(tmp_name)
