import pytest

from tests.support.fixtures import base_data


@pytest.fixture
def data():
    return base_data()
