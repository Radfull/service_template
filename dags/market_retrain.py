from datetime import UTC, datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import CronTriggerTimetable, Param, dag, task
from kubernetes.client import models as k8s

PULL = "uv run --no-sync dvc pull -r cluster pipelines/data/data.csv && "
ENV = {"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000", "MODEL_NAME": "market_model"}
COMMON = dict(
    namespace="mlops",
    in_cluster=True,
    image="{{ var.value.market_image }}",
    image_pull_policy="IfNotPresent",
    get_logs=True,
    on_finish_action="delete_pod",
    env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
)


@dag(
    schedule=CronTriggerTimetable("0 3 * * *", timezone="Europe/Moscow"),
    catchup=False,
    max_active_runs=1,
    params={"C": Param(1.0, type="number", exclusiveMinimum=0)},
    tags=["market"],
)
def market_retrain():
    validate = KubernetesPodOperator(
        task_id="validate",
        name="market-validate",
        env_vars=ENV,
        cmds=["sh", "-c", PULL + "uv run --no-sync python -m market.data"],
        **COMMON,
    )
    train = KubernetesPodOperator(
        task_id="train",
        name="market-train",
        env_vars={**ENV, "C": "{{ params.C }}"},
        cmds=["sh", "-c", PULL + "uv run --no-sync python -m market.train"],
        do_xcom_push=True,
        **COMMON,
    )

    @task.short_circuit
    def promoted(result: dict) -> bool:
        print(result)
        return result["promoted"]

    @task
    def rollout():
        from kubernetes import client, config

        config.load_incluster_config()
        client.AppsV1Api().patch_namespaced_deployment(
            "market-service",
            "default",
            {"spec": {"template": {"metadata": {"annotations": {
                "kubectl.kubernetes.io/restartedAt": datetime.now(UTC).isoformat()
            }}}}},
        )

    validate >> train
    promoted(train.output) >> rollout()


market_retrain()
