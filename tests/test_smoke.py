import pytest


def test_predict_smoke(client, good_row):
    r = client.post("/v1/predict", json=good_row)
    assert r.status_code == 200
    body = r.json()
    assert body["segmentation"] in ['A', 'B', 'C', 'D']
    assert body["latency_ms"] >= 0
    assert body["model_version"]


def test_predict_handles_missing_total_charges(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "age": None})
    assert r.status_code == 422


def test_batch_and_single_agree(client, good_row):
    s1 = client.post("/v1/predict", json=good_row).json()["probs"]
    s2 = client.post("/v1/predict", json=good_row).json()["probs"]
    assert s1.keys() == s2.keys()
    for k in s1:
        assert s1[k] == pytest.approx(s2[k])