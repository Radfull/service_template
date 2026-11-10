from prometheus_client.parser import text_string_to_metric_families


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "service_version" in r.json()

def test_ready(client):
    assert client.get("/ready").status_code == 200


def test_metrics_report_loaded_model(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    samples = [
        sample
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
        if sample.name == "market_model_info"
    ]
    assert len(samples) == 1
    assert samples[0].value == 1
    assert samples[0].labels["version"] == client.get("/health").json()["model_version"]


def test_metrics_count_successful_predictions(client, good_row):
    def prediction_count():
        return sum(
            sample.value
            for family in text_string_to_metric_families(client.get("/metrics").text)
            for sample in family.samples
            if sample.name == "market_predictions_total"
        )

    before = prediction_count()
    assert client.post("/v1/predict", json=good_row).status_code == 200
    assert prediction_count() == before + 1

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
