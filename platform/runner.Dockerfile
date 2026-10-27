FROM myoung34/github-runner:ubuntu-noble

USER root
ARG TARGETARCH
ARG KIND_VERSION
ARG KUBECTL_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl jq python3 && rm -rf /var/lib/apt/lists/*
RUN test -n "$KIND_VERSION" && test -n "$KUBECTL_VERSION" && test -n "$TARGETARCH"
RUN curl -fsSL "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${TARGETARCH}" -o /usr/local/bin/kind && chmod +x /usr/local/bin/kind
RUN curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" -o /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl
RUN usermod -aG root runner
RUN command -v docker && command -v git && command -v kind && command -v kubectl && command -v python3 && command -v curl && command -v jq
