#!/usr/bin/env bash
# Платформа одной командой: kind с портом 80, Traefik, MLflow, Airflow, S3 (RustFS), Prometheus и Grafana.
# Повторный запуск безопасен: что уже стоит, только обновится.
#
#   bash platform/up.sh                    кластер market-cluster, порт 80
#   CLUSTER=market-check HOST_PORT=18080 bash platform/up.sh
#
# Ключи S3 по умолчанию учебные. Свои: S3_KEY=... S3_SECRET=... bash platform/up.sh
set -euo pipefail
CLUSTER=${CLUSTER:-market-cluster}
HOST_PORT=${HOST_PORT:-80}
S3_KEY=${S3_KEY:-dvcadmin}
S3_SECRET=${S3_SECRET:-dvc-secret-123}
cd "$(dirname "$0")/.."

if [[ ! "$HOST_PORT" =~ ^[1-9][0-9]{0,4}$ ]] || (( HOST_PORT > 65535 )); then
  echo "HOST_PORT должен быть числом от 1 до 65535" >&2
  exit 1
fi
for tool in docker kind kubectl helm curl; do
  command -v "$tool" >/dev/null || { echo "Не найден $tool" >&2; exit 1; }
done
docker info >/dev/null
PLATFORM_TMP=$(mktemp -d)
trap 'rm -f "$PLATFORM_TMP/image.tar" "$PLATFORM_TMP/kind-config.yaml"; rmdir "$PLATFORM_TMP"' EXIT

echo "== кластер $CLUSTER"
if kind get clusters | grep -qx "$CLUSTER"; then
  mapping=$(docker port "$CLUSTER-control-plane" 30080/tcp)
  if ! printf '%s\n' "$mapping" | grep -q ":$HOST_PORT$"; then
    echo "У кластера $CLUSTER другой проброс порта: $mapping; запустите с нужным HOST_PORT" >&2
    exit 1
  fi
else
  sed "s/hostPort: 80/hostPort: $HOST_PORT/" platform/kind-config.yaml > "$PLATFORM_TMP/kind-config.yaml"
  kind create cluster --name "$CLUSTER" --config "$PLATFORM_TMP/kind-config.yaml"
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "== образы, скачанные заранее (docker pull), кладём прямо в узел"
# kind load docker-image падает на мультиплатформенных образах, если Docker Desktop хранит их в containerd
# ("content digest ... not found"), поэтому через архив одной платформы
ARCH=$(docker version --format '{{.Server.Arch}}')
for img in apache/airflow:3.3.2 ghcr.io/mlflow/mlflow:v3.16.1 rustfs/rustfs:1.0.0; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "  загружаем $img (большой образ может занять несколько минут)"
    docker save --platform "linux/$ARCH" "$img" -o "$PLATFORM_TMP/image.tar" \
      && kind load image-archive "$PLATFORM_TMP/image.tar" --name "$CLUSTER" >/dev/null && echo "  $img"
  fi
done

echo "== MLflow, S3, Airflow"
kubectl apply -f platform/mlflow.yaml
kubectl -n mlops create secret generic s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID="$S3_KEY" --from-literal=AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f platform/s3.yaml -f platform/airflow.yaml

echo "== Traefik, Prometheus и Grafana"
helm repo add traefik https://traefik.github.io/charts >/dev/null 2>&1 || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
repos_ready=false
for attempt in 1 2 3; do
  if helm repo update traefik prometheus-community; then
    repos_ready=true
    break
  fi
  echo "Не удалось обновить индексы Helm, попытка $attempt из 3" >&2
  sleep 3
done
if [[ "$repos_ready" != true ]]; then
  echo "Проверьте доступ к traefik.github.io и prometheus-community.github.io" >&2
  exit 1
fi
helm upgrade --install traefik traefik/traefik --version 41.6.0 \
  -n traefik --create-namespace -f platform/traefik-values.yaml --wait --timeout=15m
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 91.5.2 \
  -n monitoring --create-namespace -f platform/monitoring-values.yaml --wait --timeout=15m
kubectl apply -f platform/ingress.yaml

echo "== ждём поды"
kubectl -n mlops rollout status deploy/mlflow deploy/rustfs deploy/airflow --timeout=15m
kubectl -n monitoring rollout status deploy/monitoring-grafana --timeout=15m

echo "== бакет dvc в S3"
bucket_ready=false
for i in $(seq 1 30); do
  code=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' -X PUT --aws-sigv4 "aws:amz:us-east-1:s3" \
    --user "$S3_KEY:$S3_SECRET" "http://s3.localhost:$HOST_PORT/dvc") || code=000
  case $code in 200|409) echo "бакет dvc есть ($code)"; bucket_ready=true; break ;; esac
  echo "Попытка $i: HTTP $code"
  sleep 2
done
if [[ "$bucket_ready" != true ]]; then
  echo "Не удалось создать бакет dvc; проверьте Ingress и ключи S3" >&2
  exit 1
fi

echo
echo "Готово:  http://mlflow.localhost:$HOST_PORT  http://airflow.localhost:$HOST_PORT"
echo "         http://grafana.localhost:$HOST_PORT (admin/admin)"
echo "         http://s3-console.localhost:$HOST_PORT/rustfs/console/index.html (учётные данные S3)"
