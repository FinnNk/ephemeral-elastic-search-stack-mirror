FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844

ARG TARGETARCH
ARG KUBECTL_VERSION=v1.35.8
ARG HELM_VERSION=v4.3.0

RUN apk add --no-cache ca-certificates curl git libstdc++ && \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" -o /usr/local/bin/kubectl && \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl.sha256" -o /tmp/kubectl.sha256 && \
    echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum -c - && \
    curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" -o /tmp/helm.tar.gz && \
    curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum" -o /tmp/helm.sha256 && \
    echo "$(cut -d ' ' -f 1 /tmp/helm.sha256)  /tmp/helm.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/helm.tar.gz -C /tmp "linux-${TARGETARCH}/helm" && \
    install -m 0755 "/tmp/linux-${TARGETARCH}/helm" /usr/local/bin/helm && \
    chmod 0755 /usr/local/bin/kubectl && \
    rm -rf /tmp/kubectl.sha256 /tmp/helm.sha256 /tmp/helm.tar.gz "/tmp/linux-${TARGETARCH}"

WORKDIR /app
COPY lab/control-runtime/requirements.lock /tmp/requirements.lock
RUN apk add --no-cache --virtual .build-deps build-base && \
    pip install --no-cache-dir -r /tmp/requirements.lock && \
    apk del .build-deps

COPY lab/ /app/lab/
COPY research/platform-spike/ /app/research/platform-spike/

ENV LAB_IN_CLUSTER=1 LAB_STATE_DIR=/state PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
USER 10001:10001
EXPOSE 18082
