import os

import psycopg
import pytest

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="нужен Postgres: задайте DATABASE_URL"),
]


def test_prediction_is_logged(client, good_row):
    body = client.post("/v1/predict", json=good_row).json()

    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT model_version, probs, features->'age', response_status "
            "FROM predictions WHERE request_id = %s",
            (body["request_id"],),
        ).fetchone()

    assert row is not None
    assert row[0] == body["model_version"]

    assert row[1].keys() == body["probs"].keys()
    for k in body["probs"]:
        assert row[1][k] == pytest.approx(body["probs"][k])

    assert row[2] == good_row["age"]
    assert row[3] == 200


def test_invalid_prediction_is_logged_with_422(client, good_row):
    body = client.post("/v1/predict", json={**good_row, "age": -1}).json()

    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT response_status, segmentation "
            "FROM predictions WHERE request_id = %s",
            (body["request_id"],),
        ).fetchone()

    assert row is not None
    assert row[0] == 422
    assert row[1] == "INVALID"