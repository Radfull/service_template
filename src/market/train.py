import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import pandas as pd
import sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path(os.getenv("DATA_PATH", "pipelines/data/data.csv"))
MODEL_NAME = os.getenv("MODEL_NAME", "market_model")
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "market")
MIN_GAIN = float(os.getenv("GATE_MIN_GAIN", "0.0"))
SEED = 42
SKOPS_TRUSTED = ["numpy.dtype", "sklearn.compose._column_transformer._RemainderColsList"]

TARGET = "segmentation"
C = float(os.getenv("C", "1.0"))
NUM_FEATURES = ["age", "work_experience", "family_size"]
CAT_FEATURES = ["gender", "ever_married", "graduated", "spending_score"]
CLASS_LABELS = {"A": 0, "B": 1, "C": 2, "D": 3}


def get_file_md5(path: Path) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_and_validate(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(NUM_FEATURES + CAT_FEATURES + [TARGET]) - set(df.columns)
    if missing:
        raise ValueError(f"в данных нет колонок: {sorted(missing)}, представлено {df.columns}")
    if len(df) < 100:
        raise ValueError(f"слишком мало строк: {len(df)}")
    if not set(df[TARGET].unique()) <= set(CLASS_LABELS.keys()):
        raise ValueError(f"неожиданные значения таргета: {df[TARGET].unique()[:5]}")
    
    df["target"] = df[TARGET].map(CLASS_LABELS)
    return df


def build_pipeline(c:float) -> Pipeline:
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent"))
    ])
    preprocessor = ColumnTransformer([
        ("num", numeric_pipe, NUM_FEATURES),
        ("cat", categorical_pipe, CAT_FEATURES),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("model", LogisticRegression(C=c, random_state=SEED)),
    ])


def get_champion_metric(client: MlflowClient) -> tuple[str | None, float | None]:
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        return None, None
    run = client.get_run(mv.run_id)
    return mv.version, run.data.metrics.get("f1_macro")


def main() -> dict:
    df = load_and_validate(DATA_PATH)
    data_md5 = get_file_md5(DATA_PATH)
    features = NUM_FEATURES + CAT_FEATURES
    
    x_train, x_test, y_train, y_test = train_test_split(
        df[features], df["target"], test_size=0.2, stratify=df["target"], random_state=SEED
    )

    pipeline = build_pipeline(C).fit(x_train, y_train)
    preds = pipeline.predict(x_test)
    f1_macro = float(f1_score(y_test, preds, average="macro"))

    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()
    
    with mlflow.start_run() as run:
        metadata = {
            "model_version": "1.0",
            "trained_at": datetime.now(UTC).isoformat(),
            "sklearn_version": sklearn.__version__,
            "target": TARGET,
            "features": features,
            "numeric_features": NUM_FEATURES,
            "categorical_features": CAT_FEATURES,
            "threshold": 0.5,
            "class_labels": CLASS_LABELS,
            "n_train": len(x_train),
            "data_rows": len(df)
        }
        
        mlflow.log_params({
            "model": "LogisticRegression", 
            "C" : C, 
            "seed": SEED, 
            "data_path": str(DATA_PATH),
            "data_md5": data_md5
        })
        
        mlflow.log_metrics({"f1_macro": f1_macro})
        mlflow.log_dict(metadata, "metadata.json")
        
        cm = confusion_matrix(y_test, preds)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=list(CLASS_LABELS.keys()))
        disp.plot(cmap=plt.cm.Blues)
        plt.title("Confusion Matrix")
        mlflow.log_figure(disp.figure_, "confusion_matrix.png")
        plt.close(disp.figure_)
        
        info = mlflow.sklearn.log_model(
            pipeline, 
            name="model", 
            registered_model_name=MODEL_NAME, 
            skops_trusted_types=SKOPS_TRUSTED
        )
        version = info.registered_model_version

    old_version, old_metric = get_champion_metric(client)
    promoted = old_metric is None or f1_macro > old_metric + MIN_GAIN
    
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)

    result = {
        "run_id": run.info.run_id,
        "version": version,
        "f1_macro": round(f1_macro, 4),
        "data_md5": data_md5,
        "champion_before": old_version,
        "champion_metric_before": old_metric,
        "promoted": promoted,
    }
    
    print(json.dumps(result, ensure_ascii=False))
    
    xcom = Path("/airflow/xcom")
    if xcom.is_dir():
        (xcom / "return.json").write_text(json.dumps(result))
        
    return result


if __name__ == "__main__":
    main()