def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "service_version" in r.json()

def test_ready(client):
    assert client.get("/ready").status_code == 200

def test_bad_tenure_is_422(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "age": -1})
    assert r.status_code == 422

def test_missing_field_is_422(client, good_row):
    row = dict(good_row)
    del row["age"]
    assert client.post("/v1/predict", json=row).status_code == 422

def test_extra_field_is_422(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "hacker_field": 1})
    assert r.status_code == 422