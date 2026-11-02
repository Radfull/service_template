import json
from pathlib import Path

from locust import HttpUser, between, task


PAYLOAD = json.loads(
    (Path(__file__).parent.parent / "tests" / "good.json").read_text(
        encoding="utf-8"
    )
)

class MarketUser(HttpUser):
    wait_time = between(0.05, 0.15)

    @task
    def predict(self):
        self.client.post(
            "/v1/predict",
            json=PAYLOAD,
            timeout=30,
        )