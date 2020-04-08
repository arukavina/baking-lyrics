#!/usr/bin/env python
'''
Modeling Classes
'''

# Generic
import tempfile
import os

# Libs
import boto3
from botocore import exceptions
import pandas as pd

# Own
from baking.main.util import log_utils

logger = log_utils.get_logger('baking-api')

logger.info('Logging to AWS and accessing s3 resource')
s3 = boto3.resource('s3', region_name='us-east-2')
logger.info('Connecting to BL bucket')
bucket = s3.Bucket('bakinglyrics')


def read_bucket_object(object_name):
    """
    Reads S3 Bucket object
    :param object_name: Object path.
    :return: s3_object a tmp
    """

    s3_object = bucket.Object(object_name)
    return s3_object


def read_s3_csv_as_tmpfile(object_name=None):

    if object is None:
        raise AttributeError('Object argument can not be None.')

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


def read_s3_h5_as_tmpfile(object_name=None):

    s3_object = read_bucket_object(object_name)
    tmp = tempfile.NamedTemporaryFile()

    if object is None:
        raise AttributeError('Object argument can not be None.')

    from keras.models import load_model
    from keras_self_attention import SeqSelfAttention

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

        s3_model = load_model(tmp.name, compile=False, custom_objects=SeqSelfAttention.get_custom_objects())

    return s3_model


if __name__ == '__main__':

    logger.info('PWD = {}'.format(os.getcwd()))

    print('Reading CSV')
    df = read_s3_csv_as_tmpfile('resources/songdata_4_tests.csv')
    print(df.head())

    print('Reading Model')
    model = read_s3_h5_as_tmpfile('resources/models/lyrics_skth_v0_20_40_300_5000_100.model.generator_word.h5')
    print(model)
