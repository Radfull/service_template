import pytest
from fastapi.testclient import TestClient

from market.service.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def good_row():
    return {
    "age": 20,
    "work_experience": 1,
    "family_size": 3,
    "gender": True,
    "ever_married": True,
    "graduated": True,
    "spending_score": 0
    }
