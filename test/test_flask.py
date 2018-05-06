import os
from baking_api import app
import pytest
import unittest
import tempfile


@pytest.fixture(scope='module')
def test_client():
    testing_client = app.test_client()

    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()

    yield testing_client  # this is where the testing happens!

    ctx.pop()


def test_root(test_client):
    response = test_client.get('/')
    assert response.status_code == 404
