import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import pandas as pd
import pandera.pandas as pa

DATA = Path(os.getenv("DATA_PATH", "pipelines/data/data.csv"))
ROWS = pa.DataFrameSchema({
    "age": pa.Column(int, pa.Check.in_range(18, 100)),
    "work_experience": pa.Column(float, pa.Check.in_range(0, 80)),
    "family_size": pa.Column(int, pa.Check.in_range(1, 20)),
    "gender": pa.Column(int, pa.Check.isin([0, 1])),
    "ever_married": pa.Column(int, pa.Check.isin([0, 1])),
    "graduated": pa.Column(int, pa.Check.isin([0, 1])),
    "spending_score": pa.Column(int, pa.Check.isin([0, 1, 2])),
    "segmentation": pa.Column(str, pa.Check.isin(list("ABCD"))),
}, strict=True)
EXPORT = pa.DataFrameSchema(ROWS.columns, checks=[
    pa.Check(lambda df: len(df) >= 1000, error="too_few_rows"),
    pa.Check(
        lambda df: df["segmentation"].value_counts(normalize=True)
        .reindex(list("ABCD"), fill_value=0).between(0.15, 0.35).all(),
        error="class_share_outside_15_35_percent",
    ),
], strict=True)


def main():
    df = pd.read_csv(DATA)
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "market"))
    with mlflow.start_run(run_name="validate"):
        mlflow.log_params({
            "step": "validate", "data_md5": hashlib.md5(DATA.read_bytes()).hexdigest()
        })
        mlflow.log_metric("data_rows", len(df))
        mlflow.set_tag("valid", "false")
        try:
            EXPORT.validate(df, lazy=True)
        except pa.errors.SchemaErrors as exc:
            with TemporaryDirectory() as directory:
                report = Path(directory) / "failure_cases.csv"
                exc.failure_cases.to_csv(report, index=False)
                mlflow.log_artifact(str(report))
            raise
        mlflow.set_tag("valid", "true")


if __name__ == "__main__":
    main()