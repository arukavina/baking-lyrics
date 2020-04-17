#!/usr/bin/env python

# Generic
import tempfile
import os

# Libs
import pandas as pd
import numpy as np

import boto3
from botocore import exceptions
from flask import current_app as app

# Own
from baking.main.util import log_utils

logger = log_utils.get_logger('baking-api')

# print('Current wd={}'.format(os.getcwd()))
#
# from flask import Flask
#
# app = Flask("baking-lyrics",
#             static_folder="baking/static/dist",
#             template_folder="baking/static")
#
# app.config.from_object('config.default')
# app.config.from_object('config.production')

logger.info('Logging to AWS and accessing [s3] resource')
s3 = boto3.resource('s3', region_name=app.config['AWS_REGION'])

logger.info('Connecting to AWS bucket: {}'.format(app.config['AWS_BUCKET']))
bucket = s3.Bucket(app.config['AWS_BUCKET'])


def read_bucket_object(object_name):
    """
    Reads S3 Bucket object
    :param object_name: Object path.
    :return: s3_object a tmp
    """

    s3_object = bucket.Object(object_name)
    return s3_object


def read_s3_csv_as_tmpfile(object_name=None):

    if object_name is None:
        raise AttributeError('object_name argument can not be None.')

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile()

    with open(tmp.name, 'wb') as f:
        try:
            s3_object.download_fileobj(f)
        except exceptions.ClientError as e:
            logger.debug(e.response)
            if e.response['Error']['Code'] == '404':
                logger.error('File does not exist: {}'.format(object_name))
            else:
                logger.error('Unexpected error: %s' % e)
                raise RuntimeError(e)
            raise FileNotFoundError(e)

        csv_object = pd.read_csv(tmp.name)

    return csv_object


def read_s3_h5_as_tmpfile(object_name=None, custom_objects=None):

    if object_name is None:
        raise AttributeError('object_name argument can not be None.')

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile()

    from keras.models import load_model

    with open(tmp.name, 'wb') as f:
        try:
            s3_object.download_fileobj(f)
        except exceptions.ClientError as e:
            logger.debug(e.response)
            if e.response['Error']['Code'] == '404':
                logger.error('File does not exist: {}'.format(object_name))
            else:
                logger.error('Unexpected error: %s' % e)
                raise RuntimeError(e)
            raise FileNotFoundError(e)

    if custom_objects is not None:
        s3_model = load_model(tmp.name, compile=False, custom_objects=custom_objects)
    else:
        s3_model = load_model(tmp.name, compile=False)

    return s3_model


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

    if object_name is None:
        raise AttributeError('object_name argument can not be None.')

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile()

    with open(tmp.name, 'wb') as f:
        try:
            s3_object.download_fileobj(f)
        except exceptions.ClientError as e:
            logger.debug(e.response)
            if e.response['Error']['Code'] == '404':
                logger.error('File does not exist: {}'.format(object_name))
            else:
                logger.error('Unexpected error: %s' % e)
                raise RuntimeError(e)
            raise FileNotFoundError(e)

        pickle_object = np.load(tmp.name, allow_pickle=allow_pickle)

    return pickle_object


def read_s3_pickle_tmp(object_name):
    if object_name is None:
        raise AttributeError('object_name argument can not be None.')

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile()

    with open(tmp.name, 'wb') as f:
        try:
            s3_object.download_fileobj(f)
        except exceptions.ClientError as e:
            logger.debug(e.response)
            if e.response['Error']['Code'] == '404':
                logger.error('File does not exist: {}'.format(object_name))
            else:
                logger.error('Unexpected error: %s' % e)
                raise RuntimeError(e)
            raise FileNotFoundError(e)

    return tmp


if __name__ == '__main__':

    logger.info('PWD = {}'.format(os.getcwd()))

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
