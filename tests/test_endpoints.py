import pytest
from api.v1 import endpoints
from api.v1 import restplus
import os
import api

import flask
import unittest
import tempfile
import mock
from flask import request
import api.server as ap


@pytest.fixture(scope='module')
def test_client():
    testing_client = ap.app.test_client()
    # Establish an application context before running the tests.
    ctx = ap.app.app_context()
    ctx.push()
    yield testing_client  # this is where the testing happens!
    ctx.pop()


def test_root(test_client):
    response = test_client.get('/general/ping')
    assert response.status_code == 200
    data = str(response.data.decode('utf8'))
    assert data == 'pong!'




