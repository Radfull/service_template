# ДЗ 4: минимальные изменения для market-service

Основа — [коммит занятия](https://github.com/artemovmak/ML_PRO2026/tree/479fceba7e228b9515c73d1e6affc2c0a8eede9c).
Нужны **четыре новых технических файла**: `src/market/data.py`, `tests/test_data.py`,
`dags/market_retrain.py`, `k8s/monitoring.yaml`. Остальное — правки существующих файлов
и обязательный `REPORT.md`. Пункты 4–8 применены к проекту; ниже сохранены код и порядок действий.

В эталоне [churn DAG](https://github.com/artemovmak/ML_PRO2026/blob/479fceba7e228b9515c73d1e6affc2c0a8eede9c/dags/churn_retrain.py)
содержит три задачи. Добавляем validate по образцу
[recs DAG](https://github.com/artemovmak/ML_PRO2026/blob/479fceba7e228b9515c73d1e6affc2c0a8eede9c/dags/recs_retrain.py),
а Pandera адаптируем из [recs/data.py](https://github.com/artemovmak/ML_PRO2026/blob/479fceba7e228b9515c73d1e6affc2c0a8eede9c/src/churn/recs/data.py).

## 1. Ветка, S3 и Dockerfile

```powershell
git switch -c hw04
uv sync --frozen
$env:NO_PROXY = 'localhost,127.0.0.1,.localhost'
& "C:\Program Files\Git\bin\bash.exe" platform/up.sh
uv run dvc remote modify --local laptop access_key_id dvcadmin
uv run dvc remote modify --local laptop secret_access_key dvc-secret-123
uv run dvc push -r laptop
```

Платформа, remotes, MLflow-гейт и права Airflow уже есть — повторно их создавать не нужно.
NO_PROXY исключает локальные адреса из системного прокси; без него DVC на этой машине получал 503 от HeadObject.
Из Python должны разрешаться `s3.localhost` и `mlflow.localhost`; при необходимости добавьте их в hosts.
В Dockerfile после `COPY artifacts/ artifacts/` добавьте:

```dockerfile
COPY .dvc/config .dvc/config
COPY pipelines/data/*.dvc pipelines/data/
RUN uv run --no-sync dvc config --local core.no_scm true
ARG GIT_SHA=local
ENV GIT_SHA=$GIT_SHA
```

Ваш .dockerignore уже исключает CSV и DVC cache. После сборки выполните
`docker run --rm <образ> ls -la pipelines/data`: должен быть только указатель, без CSV.
Сохраните вывод и скрин бакета.

## 2. Создайте src/market/data.py

CSV содержит 6690 строк, без пропусков; возраст 18–89, опыт 0–14, семья 1–9,
доли классов 24–26%. Диапазоны ниже взяты с запасом; минимум 1000 строк ловит усечение,
коридор 15–35% — сильный сдвиг классов. Это обоснование перенесите в отчёт.
Идентификатора в CSV нет, проверка уникальности не нужна.

```python
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
```

В train.py добавьте `from market.data import EXPORT`, замените только load_and_validate:

```python
def load_and_validate(path: Path) -> pd.DataFrame:
    df = EXPORT.validate(pd.read_csv(path), lazy=True)
    df["target"] = df[TARGET].map(CLASS_LABELS)
    return df
```

В существующий `mlflow.log_params` добавьте `"git_sha": os.getenv("GIT_SHA", "local")`.
Ваши data_md5, гейт, алиасы и XCom уже реализованы — оставьте их.

## 3. Создайте tests/test_data.py

```python
import pandas as pd
import pandera.pandas as pa
import pytest
from market.data import EXPORT, ROWS


@pytest.fixture()
def frame():
    return pd.DataFrame({
        "age": [22, 38, 49, 67], "work_experience": [1.0, 5.0, 10.0, 14.0],
        "family_size": [1, 2, 3, 4], "gender": [0, 1, 0, 1],
        "ever_married": [0, 1, 1, 1], "graduated": [0, 1, 1, 1],
        "spending_score": [0, 1, 2, 0], "segmentation": list("ABCD"),
    })


def test_good_rows(frame):
    ROWS.validate(frame, lazy=True)


def test_bad_value(frame):
    frame.loc[0, "age"] = 264
    with pytest.raises(pa.errors.SchemaErrors) as exc:
        ROWS.validate(frame, lazy=True)
    assert "age" in set(exc.value.failure_cases["column"])


def test_small_export(frame):
    with pytest.raises(pa.errors.SchemaErrors) as exc:
        EXPORT.validate(frame, lazy=True)
    assert "too_few_rows" in set(exc.value.failure_cases["check"])
```

```powershell
uv run pytest tests/test_data.py -q
```

Три теста работают без CSV и S3: хорошие строки, плохое значение, маленькая выгрузка.

## 4. Добавьте метрики в существующие модули

В service/main.py добавьте на уровне модуля:

```python
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

MODEL_INFO = Gauge("market_model_info", "Model loaded in this pod", ["version"])
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1)
```

В lifespan сразу после load_model():

```python
    MODEL_INFO.clear()
    MODEL_INFO.labels(app.state.version).set(1)
```

После создания app = FastAPI(...):

```python
Instrumentator().instrument(app, latency_lowr_buckets=LATENCY_BUCKETS).expose(app)
```

В service/api/v1/model.py на уровне модуля:

```python
from prometheus_client import Counter

PREDICTIONS = Counter("market_predictions_total", "Predictions by segment", ["segment"])
```

После успешного await cruds.create_prediction(...), перед return:

```python
    PREDICTIONS.labels(segmentation).inc()
```

Это две свои метрики: версия и сегменты. Request_id в метках нет.
После нагрузки измерьте p50/p95 полного HTTP-запроса и уточните бакеты; объясните их в отчёте.

В k8s/service.yaml добавьте `labels: {app: market}` в metadata и имя порта:

```yaml
  ports:
    - name: http
      port: 80
      targetPort: 8000
```

В k8s/deployment.yaml добавьте стратегию и lifecycle в соответствующие существующие блоки:

```yaml
# deployment.spec
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxUnavailable: 0, maxSurge: 1}

# deployment.spec.template.spec.containers[api]
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 5"]
```

## 5. Создайте k8s/monitoring.yaml

Один файл объединяет ServiceMonitor и ConfigMap дашборда.
Это сокращённый [дашборд занятия](https://github.com/artemovmak/ML_PRO2026/blob/479fceba7e228b9515c73d1e6affc2c0a8eede9c/k8s/monitoring/dashboard.yaml)
с панелями вашей модели: версия по подам, RPS, p50/p95, сегменты.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: market-service
  namespace: default
spec:
  selector:
    matchLabels: {app: market}
  endpoints:
    - {port: http, path: /metrics, interval: 15s}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: market-dashboard
  namespace: monitoring
  labels: {grafana_dashboard: "1"}
data:
  market.json: |
    {
      "uid": "market-service", "title": "Market service", "schemaVersion": 39,
      "refresh": "10s", "time": {"from": "now-30m", "to": "now"},
      "panels": [
        {
          "id": 1, "type": "timeseries", "title": "Model version by pod",
          "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
          "datasource": {"type": "prometheus", "uid": "prometheus"},
          "targets": [{"refId": "A", "expr": "market_model_info{namespace=\"default\"}", "legendFormat": "{{pod}} v{{version}}"}]
        },
        {
          "id": 2, "type": "timeseries", "title": "Predict RPS",
          "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
          "datasource": {"type": "prometheus", "uid": "prometheus"},
          "targets": [{"refId": "A", "expr": "sum(rate(http_requests_total{namespace=\"default\",handler=\"/v1/predict\"}[1m]))"}]
        },
        {
          "id": 3, "type": "timeseries", "title": "Predict latency",
          "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
          "datasource": {"type": "prometheus", "uid": "prometheus"},
          "fieldConfig": {"defaults": {"unit": "s"}},
          "targets": [
            {"refId": "A", "expr": "histogram_quantile(0.50, sum by(le)(rate(http_request_duration_seconds_bucket{namespace=\"default\",handler=\"/v1/predict\"}[1m])))", "legendFormat": "p50"},
            {"refId": "B", "expr": "histogram_quantile(0.95, sum by(le)(rate(http_request_duration_seconds_bucket{namespace=\"default\",handler=\"/v1/predict\"}[1m])))", "legendFormat": "p95"}
          ]
        },
        {
          "id": 4, "type": "timeseries", "title": "Predicted segments",
          "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
          "datasource": {"type": "prometheus", "uid": "prometheus"},
          "targets": [{"refId": "A", "expr": "sum by(segment)(rate(market_predictions_total{namespace=\"default\"}[1m]))", "legendFormat": "{{segment}}"}]
        }
      ]
    }
```

## 6. Создайте dags/market_retrain.py

Как в занятии: отдельные поды скачивают данные, short circuit управляет выкатом.
Во время запуска DAG не обновляйте его образ через CI.

```python
from datetime import UTC, datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import CronTriggerTimetable, Param, dag, task
from kubernetes.client import models as k8s

PULL = "uv run --no-sync dvc pull -r cluster pipelines/data/data.csv && "
ENV = {"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000", "MODEL_NAME": "market_model"}
COMMON = dict(
    namespace="mlops", in_cluster=True, image="{{ var.value.market_image }}",
    image_pull_policy="IfNotPresent", get_logs=True, on_finish_action="delete_pod",
    env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
)


@dag(
    schedule=CronTriggerTimetable("0 3 * * *", timezone="Europe/Moscow"),
    catchup=False, max_active_runs=1,
    params={"C": Param(1.0, type="number", exclusiveMinimum=0)},
    tags=["market"],
)
def market_retrain():
    validate = KubernetesPodOperator(
        task_id="validate", name="market-validate", env_vars=ENV,
        cmds=["sh", "-c", PULL + "uv run --no-sync python -m market.data"], **COMMON,
    )
    train = KubernetesPodOperator(
        task_id="train", name="market-train", env_vars={**ENV, "C": "{{ params.C }}"},
        cmds=["sh", "-c", PULL + "uv run --no-sync python -m market.train"],
        do_xcom_push=True, **COMMON,
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
            "market-service", "default",
            {"spec": {"template": {"metadata": {"annotations": {
                "kubectl.kubernetes.io/restartedAt": datetime.now(UTC).isoformat()
            }}}}},
        )

    validate >> train
    promoted(train.output) >> rollout()


market_retrain()
```

Как в эталоне, rollout отправляет patch. Завершение обновления проверьте отдельно:
`kubectl rollout status deploy/market-service --timeout=300s` и непрерывным трафиком.

## 7. Замените scripts/locustfile.py

Используем уже имеющийся Locust вместо нового traffic.py. Запросы идут через Ingress,
вывод покажет версии моделей и число ошибок.

```python
import json
import random
from collections import Counter
from pathlib import Path

from locust import HttpUser, between, events, task

PAYLOAD = json.loads((Path(__file__).parent.parent / "tests/good.json").read_text())
VERSIONS = Counter()


class MarketUser(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self):
        self.client.trust_env = False

    @task
    def predict(self):
        row = {**PAYLOAD, "age": random.randint(18, 89), "spending_score": random.randint(0, 2)}
        with self.client.post("/v1/predict", json=row, timeout=10, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    version = str(response.json()["model_version"])
                    if version not in VERSIONS:
                        print(f"model_version={version}", flush=True)
                    VERSIONS[version] += 1
                except (ValueError, KeyError) as exc:
                    response.failure(str(exc))


@events.quitting.add_listener
def summary(environment, **kwargs):
    print(f"versions={dict(VERSIONS)}, errors={environment.stats.total.num_failures}", flush=True)
```

## 8. Три дополнения в .github/workflows/ci.yaml

В build, в with у docker/build-push-action:

```yaml
          build-args: |
            GIT_SHA=${{ github.sha }}
```

В deploy перед smoke:

```yaml
      - name: мониторинг и DAG
        run: |
          set -euo pipefail
          kubectl apply -f k8s/monitoring.yaml
          kubectl -n mlops create configmap airflow-dags --from-file=dags/ \
            --dry-run=client -o yaml | kubectl apply -f -
          kubectl -n mlops exec deploy/airflow -- airflow variables set market_image "$IMAGE"
```

В конце существующего smoke:

```bash
VERSION=$(jq -r '.model_version.version' registry.json)
curl --fail --silent --show-error -H "Host: $INGRESS_HOST" "$INGRESS_URL/metrics" \
  | grep -F "market_model_info{version=\"$VERSION\"} 1.0"
```

Проверки реестра, строки в БД, предсказания и 422 у вас уже есть.

## 9. Тесты, PR и первый deploy

```powershell
$env:MODEL_NAME = ''
Remove-Item Env:DATABASE_URL,Env:DB_URL -ErrorAction SilentlyContinue
uv run pytest
```

Проверьте diff, закоммитьте изменения, отправьте ветку и смержите через PR в main.
Обновите локальный main. Если MLflow пустой, создайте первого champion:

```powershell
$env:MLFLOW_TRACKING_URI = 'http://mlflow.localhost'
$env:MODEL_NAME = 'market_model'
$env:GIT_SHA = git rev-parse HEAD
$env:C = '0.001'
uv run python -m market.data
uv run python -m market.train
Remove-Item Env:C,Env:MODEL_NAME,Env:MLFLOW_TRACKING_URI,Env:GIT_SHA
```

Существующего более сильного champion гейт не понизит — так и должно быть.
В этом случае демонстрацию улучшения выполните на новом пустом кластере с начальным C=0.001.
Используйте прежний runner и DB_PASSWORD. Actions → ci → Run workflow → main.
После deploy откройте Grafana → Market service и Airflow → market_retrain.
DAG может появиться через две минуты; ошибки: `kubectl -n mlops exec deploy/airflow -- airflow dags list-import-errors`.

## 10. Три обязательных сценария

**Принятие.** В отдельном терминале:

```powershell
uv run locust -f scripts/locustfile.py --headless --users 1 --spawn-rate 1 --run-time 10m --host http://market.localhost --csv results/hw04
```

В Airflow снимите DAG с паузы, Trigger DAG: C=1.0. На текущих данных после C=0.001
macro-F1 растёт примерно 0.3870 → 0.4041; против произвольного старого champion это не гарантируется.
Проверьте завершение rollout. Сохраните граф DAG, Aliases, переключение версии в Grafana
и итог Locust с errors=0. Файлы CSV Locust сохраняются в существующую папку results/.

**Отклонение.** Повторите C=1.0 на том же образе. Равный F1 не проходит ваш строгий гейт:
новый challenger, прежний champion, rollout skipped. Зафиксируйте pod UID/start time
до и после; между снимками не запускайте CI и дополнительную нагрузку, меняющую HPA.
Задача promoted может быть success: она успешно вернула false.

**Плохая выгрузка.** В новой ветке:

```powershell
uv run python -c "import pandas as pd; p='pipelines/data/data.csv'; d=pd.read_csv(p); d['age']*=12; d.to_csv(p,index=False)"
uv run dvc add pipelines/data/data.csv
uv run dvc push -r laptop
```

После dvc push закоммитьте указатель, отправьте ветку, смержите PR и выполните deploy.
Запустите DAG: validate красный; в MLflow valid=false и failure_cases.csv; API отвечает
прежним champion. Сохраните доказательства.
Через отдельный PR сделайте git revert коммита с плохим указателем; локально выполните
`uv run dvc checkout --force` (или dvc pull, если объекта нет в cache), затем deploy и DAG.
После восстановления validate/train проходят; rollout может быть skipped из-за равного F1.

## 11. REPORT.md и Quickstart

В REPORT.md нужны: схема системы; таблица хранения код/данные/модель/образ/запросы;
таблица «пункт → прогон/скрин/коммит»; восемь ответов из PDF по 2–4 предложения;
журнал проблем и переделки по старому фидбэку. Достаточная схема:

```text
Клиент → Traefik → market-service → Postgres
                     ↓ при старте
                 MLflow champion
Airflow → validate → train → promoted → rollout
            ↑        ↑        ↓
            S3/DVC       MLflow registry
Prometheus → /metrics; Grafana → Prometheus
GitHub Actions → GHCR → self-hosted runner → kind
```

В существующем README замените `...` точными командами:
clone → uv sync → platform/up.sh → восстановление CSV → dvc push → первый champion
→ runner / DB_PASSWORD → Run workflow → curl через Ingress. Укажите адреса UI и ручной Trigger DAG.

Для нового пустого S3 нужен исходный CSV. Без bootstrap-скрипта можно один раз
приложить хороший CSV к GitHub Release `hw04-data`, а в Quickstart перед dvc add/push вставить:

```powershell
curl.exe --fail -L https://github.com/Radfull/service_template/releases/download/hw04-data/data.csv -o pipelines/data/data.csv
if ((Get-FileHash pipelines/data/data.csv -Algorithm MD5).Hash.ToLower() -ne 'c8ee98fd8ec9efea7ba7aca7c9e99198') { throw 'Wrong seed dataset' }
uv run dvc add pipelines/data/data.csv
```

Этот URL нужно предварительно подготовить публикацией asset; публикация не выполнена.
Рабочие версии остаются в DVC/S3. Другой доступный источник допустим, но впишите точную команду.

Регистрацию runner опишите уже применённой вами командой. Если она не сохранена,
после получения registration token в Settings → Actions → Runners:

```powershell
$kindVersion = (kind version).Split()[1]
$kubectlVersion = (kubectl version --client -o json | ConvertFrom-Json).clientVersion.gitVersion
docker build -f platform/runner.Dockerfile --build-arg "KIND_VERSION=$kindVersion" --build-arg "KUBECTL_VERSION=$kubectlVersion" -t market-runner:hw04 .
$env:RUNNER_TOKEN = Read-Host 'Registration token'
docker run -d --name market-runner-hw04 --restart unless-stopped --network kind --group-add 0 -v /var/run/docker.sock:/var/run/docker.sock -e REPO_URL=https://github.com/Radfull/service_template -e RUNNER_TOKEN -e RUNNER_SCOPE=repo -e RUNNER_NAME=market-runner-hw04 -e LABELS=kind market-runner:hw04
Remove-Item Env:RUNNER_TOKEN
```

Работающий runner повторно не создавайте. DB_PASSWORD задаётся в Secrets репозитория;
для существующей БД сохраняется её текущий пароль.
Deploy: Actions → ci → Run workflow → main, kind_cluster=market-cluster, runner_label=kind.
Завершите Quickstart проверкой:

```powershell
curl.exe --noproxy "*" --fail http://market.localhost/health
curl.exe --noproxy "*" --fail -H "Content-Type: application/json" --data-binary "@tests/good.json" http://market.localhost/v1/predict
```

Проверьте README в свежем клоне на новом кластере без переноса прежних CSV/cache/.venv,
замерьте время до HTTP 200. Перед удалением старого kind сохраните исходные данные и
доказательства: удаление уничтожает MLflow и S3 внутри него.

Задания со звёздочками (рекомендации, дрейф, алерт) в это базовое решение не входят.

