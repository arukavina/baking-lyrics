#!/usr/bin/env python

# Generic
import os
import tempfile

import boto3
import numpy as np

# Libs
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
    s3 = boto3.resource('s3', region_name=app.config['AWS_REGION'])

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


def read_s3_h5_as_tmpfile(object_name=None, custom_objects=None):

    from keras.models import load_model

    tmp_name = _download_to_tmpfile(object_name)
    try:
        if custom_objects is not None:
            return load_model(tmp_name, compile=False, custom_objects=custom_objects)
        return load_model(tmp_name, compile=False)
    finally:
        os.remove(tmp_name)


def read_s3_pickle_as_tmpfile(object_name, allow_pickle=False):
    """
    # Loads arrays or pickled objects from ``.npy``, ``.npz`` or pickled files from the AWS Cloud
    :param object_name: S3 Resource Name
    :param allow_pickle : bool, optional
        Allow loading pickled object arrays stored in npy files. Reasons for
        disallowing pickles include security, as loading pickled data can
        execute arbitrary code. If pickles are disallowed, loading object
        arrays will fail. Default: False
    :return: np pickle
    """

    tmp_name = _download_to_tmpfile(object_name)
    try:
        with np.load(tmp_name, allow_pickle=allow_pickle) as npz:
            # Materialise the arrays so the file can be removed
            return {key: npz[key] for key in npz.files}
    finally:
        os.remove(tmp_name)


def read_s3_pickle_tmp(object_name):
    """
    Downloads an S3 object and returns the path of the local temporary copy.
    The caller is responsible for removing it (os.remove) once done.
    """
    return _download_to_tmpfile(object_name)


if __name__ == '__main__':

    logger.info(f'PWD = {os.getcwd()}')

    print('Reading CSV')
    df = read_s3_csv_as_tmpfile('resources/songdata_4_tests.csv')
    print(df.head())

    from keras_self_attention import SeqSelfAttention
    print('Reading Model')
    model = read_s3_h5_as_tmpfile('resources/models/lyrics_skth_v0_20_40_300_5000_100.model.generator_word.h5',
                                  custom_objects=SeqSelfAttention.get_custom_objects())
    print(model)

    print('Reading Artist/Genre Tokenizer')
    agt = read_s3_pickle_as_tmpfile('resources/models/lyrics_skth_v0_20_40_300_5000_100.artist_genre_tokenizer.npz',
                                    allow_pickle=True)
    print(agt)

    print('Reading Embedding Matrix')
    em = read_s3_pickle_as_tmpfile('resources/models/lyrics_skth_v0_20_40_300_5000_100.embmat.npz')
    print(em)

    print('Reading Tokenizer')
    _tokenizer = read_s3_pickle_tmp('resources/models/lyrics_skth_v0_20_40_300_5000_100.tokenizer.pickle')
    print(_tokenizer)
    os.remove(_tokenizer)
