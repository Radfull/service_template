import json
import random
from collections import Counter
from pathlib import Path

from locust import HttpUser, between, events, task

PAYLOAD = json.loads(
    (Path(__file__).parent.parent / "tests" / "good.json").read_text(
        encoding="utf-8"
    )
)
VERSIONS = Counter()


class MarketUser(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self):
        self.client.trust_env = False

    @task
    def predict(self):
        row = {**PAYLOAD, "age": random.randint(18, 89), "spending_score": random.randint(0, 2)}
        with self.client.post("/v1/predict", json=row, timeout=10, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Expected HTTP 200, got {response.status_code}")
                return
            try:
                version = str(response.json()["model_version"])
                if version not in VERSIONS:
                    print(f"model_version={version}", flush=True)
                VERSIONS[version] += 1
            except (ValueError, KeyError, TypeError) as exc:
                response.failure(str(exc))


@events.quitting.add_listener
def summary(environment, **kwargs):
    print(f"versions={dict(VERSIONS)}, errors={environment.stats.total.num_failures}", flush=True)
