import pytest


def test_predict_smoke(client, good_row):
    r = client.post("/v1/predict", json=good_row)
    assert r.status_code == 200
    body = r.json()
    assert body["segmentation"] in ["A", "B", "C", "D"]
    assert body["latency_ms"] >= 0
    assert body["model_version"]
    assert body["response_status"] == 200

    probs = body["probs"]
    assert set(probs) == {"A", "B", "C", "D"}
    for k, v in probs.items():
        assert 0.0 <= v <= 1.0, f"probs[{k}]={v}"
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)
    assert body["segmentation"] == max(probs, key=probs.get)


def test_predict_rejects_invalid_input(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "age": None})
    assert r.status_code == 422
    body = r.json()
    assert "request_id" in body
    assert body["detail"]


def test_predict_depends_on_input(client, good_row):
    a = {**good_row, "age": 22, "work_experience": 0.0, "family_size": 1, "spending_score": 0}
    b = {**good_row, "age": 67, "work_experience": 10.0, "family_size": 6, "spending_score": 2}
    s1 = client.post("/v1/predict", json=a).json()["probs"]
    s2 = client.post("/v1/predict", json=b).json()["probs"]
    assert s1 != s2