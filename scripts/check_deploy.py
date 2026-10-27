"""Validate registry-backed inference during the deploy smoke check."""

import json
import math
import os
from pathlib import Path
from uuid import UUID


def validate(health, registry, prediction, *, model_name, model_alias):
    expected = registry["model_version"]
    version = str(expected["version"])
    if (
        health.get("status") != "ok"
        or health.get("model_source") != "mlflow"
        or health.get("model_name") != model_name
        or health.get("model_alias") != model_alias
        or health.get("model_version") != version
        or health.get("model_run_id") != expected["run_id"]
    ):
        raise ValueError(f"Health does not match registry alias: {health}")
    if prediction.get("model_version") != version or prediction.get("response_status") != 200:
        raise ValueError(f"Prediction version/status mismatch: {prediction}")

    probabilities = prediction["probs"]
    if set(probabilities) != {"A", "B", "C", "D"}:
        raise ValueError(f"Unexpected classes: {probabilities}")
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values()):
        raise ValueError(f"Invalid probabilities: {probabilities}")
    if not math.isclose(sum(probabilities.values()), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"Probabilities do not sum to one: {probabilities}")
    if prediction["segmentation"] != max(probabilities, key=probabilities.get):
        raise ValueError(f"Predicted class does not match probabilities: {prediction}")
    UUID(prediction["request_id"])


def main():
    health = json.loads(Path("health.json").read_text(encoding="utf-8"))
    registry = json.loads(Path("registry.json").read_text(encoding="utf-8"))
    prediction = json.loads(Path("pred.json").read_text(encoding="utf-8"))
    validate(
        health,
        registry,
        prediction,
        model_name=os.environ["MODEL_NAME"],
        model_alias=os.environ["MODEL_ALIAS"],
    )
    print(
        f"Registry and prediction checks passed: "
        f"model={health['model_name']} version={health['model_version']} "
        f"request_id={prediction['request_id']}"
    )


if __name__ == "__main__":
    main()
