import json
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from market.config import settings


def load_model():
    if settings.model_name:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_registry_uri(settings.mlflow_tracking_uri)
        client = MlflowClient()
        mv = client.get_model_version_by_alias(settings.model_name, settings.model_alias)
        # Resolve the alias once so the model, metadata and reported version agree.
        model_uri = f"models:/{settings.model_name}/{mv.version}"
        model = mlflow.sklearn.load_model(model_uri)
        with TemporaryDirectory() as temp_dir:
            metadata_path = client.download_artifacts(
                mv.run_id, "metadata.json", dst_path=temp_dir
            )
            metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

        if not metadata.get("features"):
            raise ValueError("metadata.json does not contain features")

        metadata.update(
            model_source="mlflow",
            model_name=settings.model_name,
            model_alias=settings.model_alias,
            registry_version=str(mv.version),
            run_id=mv.run_id,
        )
        return model, metadata, str(mv.version)

    bundle = joblib.load(settings.model_path)
    metadata = dict(bundle["metadata"])
    metadata["model_source"] = "local"
    return (
        bundle["pipeline"],
        metadata,
        str(metadata.get("model_version", "local")),
    )
