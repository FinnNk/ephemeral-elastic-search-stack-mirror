#!/bin/sh
# This script and the publisher come from protected main, never the candidate.
set -eu
: "${TRUSTED_ROOT:?}" "${SOURCE_SHA:?}" "${WORKFLOW_SOURCE_SHA:?}" "${PREVIEW_REQUEST_ID:?}"
: "${SOURCE_REPOSITORY:?}" "${RUN_ID:?}" "${RUN_ATTEMPT:?}" "${REGISTRY:?}"
: "${ARTIFACT_URL:?}" "${NEXUS_USER:?}" "${NEXUS_PASSWORD:?}"
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
export SOURCE_TREE="$(git rev-parse 'HEAD^{tree}')"
export EVENT_KIND=workflow_dispatch
PYTHON_IMAGE='python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844'
UV_IMAGE='ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946'
TOOLS="$(mktemp -d)"
UV_CONTAINER=''
export DOCKER_CONFIG="$TOOLS/docker"
cleanup() {
  if test -n "$UV_CONTAINER"; then docker rm "$UV_CONTAINER" >/dev/null; fi
  rm -rf "$TOOLS"
}
trap cleanup EXIT
UV_CONTAINER="$(docker create "$UV_IMAGE" /uv --version)"
docker cp "$UV_CONTAINER:/uv" "$TOOLS/uv"
docker rm "$UV_CONTAINER" >/dev/null
UV_CONTAINER=''
LAB_TEST_CA=/dev/null
if test -f /etc/lab-ca/root.pem; then LAB_TEST_CA=/etc/lab-ca/root.pem; fi
# Candidate tests receive neither registry credentials nor the Docker socket.
docker run --rm -i -v "$PWD:/work:ro" -v "$TRUSTED_ROOT/ci:/trusted:ro" \
  -v "$TOOLS/uv:/usr/local/bin/uv:ro" -w /work \
  -e UV_SYSTEM_CERTS=true -e UV_NO_CACHE=1 "$PYTHON_IMAGE" sh -ec '
    cat > /tmp/lab-ca.pem
    cat /etc/ssl/certs/ca-certificates.crt /tmp/lab-ca.pem > /tmp/trusted-ca.pem
    export SSL_CERT_FILE=/tmp/trusted-ca.pem
    python /trusted/versioning.py
    uv pip sync --system --require-hashes app/requirements.lock
    python -B -m unittest discover -s app -p "test_*.py" -v
  ' < "$LAB_TEST_CA"
mkdir -p "$DOCKER_CONFIG"
printf '%s' "$NEXUS_PASSWORD" | docker login "$REGISTRY" -u "$NEXUS_USER" --password-stdin
IMAGE="$REGISTRY/search-api:$SOURCE_SHA-preview-$RUN_ID-$RUN_ATTEMPT"
if test -f /etc/lab-ca/root.pem; then
  set -- --secret id=lab_ca,src=/etc/lab-ca/root.pem
else
  set --
fi
docker buildx build --platform linux/amd64,linux/arm64 "$@" \
  --label "org.opencontainers.image.revision=$SOURCE_SHA" \
  --metadata-file image-metadata.json -t "$IMAGE" --push app
docker run --rm -i -v "$PWD:/work:ro" -v "$TRUSTED_ROOT/ci:/trusted:ro" -w /work \
  -e SOURCE_SHA -e SOURCE_TREE -e SOURCE_REPOSITORY -e RUN_ID -e RUN_ATTEMPT -e EVENT_KIND \
  -e WORKFLOW_SOURCE_SHA -e PREVIEW_REQUEST_ID \
  -e REGISTRY -e ARTIFACT_URL -e NEXUS_USER -e NEXUS_PASSWORD \
  "$PYTHON_IMAGE" sh -ec '
    cat > /tmp/lab-ca.pem
    cat /etc/ssl/certs/ca-certificates.crt /tmp/lab-ca.pem > /tmp/trusted-ca.pem
    export SSL_CERT_FILE=/tmp/trusted-ca.pem
    python /trusted/release.py
  ' < "$LAB_TEST_CA"
