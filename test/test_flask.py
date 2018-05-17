import pytest

from api.v1 import restplus


@pytest.fixture(scope='module')
def test_client():
    testing_client = restplus.test_client()
    # Establish an application context before running the tests.
    ctx = restplus.app_context()
    ctx.push()

    yield testing_client  # this is where the testing happens!

    ctx.pop()


def test_root(test_client):
    response = test_client.get('/')
    assert response.status_code == 404
