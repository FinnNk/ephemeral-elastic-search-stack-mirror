#!/bin/sh
set -eu
: "${SOURCE_SHA:?}" "${SOURCE_REPOSITORY:?}" "${RUN_ID:?}" "${RUN_ATTEMPT:?}"
: "${REGISTRY:?}" "${ARTIFACT_URL:?}" "${NEXUS_USER:?}" "${NEXUS_PASSWORD:?}" "${EVENT_KIND:?}"
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
PYTHON_IMAGE='python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844'
# Run tests before giving the build access to registry credentials.
LAB_TEST_CA=/dev/null
if test -f /etc/lab-ca/root.pem; then LAB_TEST_CA=/etc/lab-ca/root.pem; fi
docker run --rm -i -v "$PWD:/work:ro" -w /work "$PYTHON_IMAGE" sh -c '
  cat > /tmp/lab-ca.pem
  if test -s /tmp/lab-ca.pem; then export PIP_CERT=/tmp/lab-ca.pem; fi
  python -m pip install --no-cache-dir -r app/requirements.lock &&
  python -B -m unittest discover -s app -p "test_*.py" -v
' < "$LAB_TEST_CA"
export DOCKER_CONFIG="$PWD/.docker-ci"
mkdir -p "$DOCKER_CONFIG"
trap 'rm -f "$DOCKER_CONFIG/config.json"' EXIT
printf '%s' "$NEXUS_PASSWORD" | docker login "$REGISTRY" -u "$NEXUS_USER" --password-stdin
IMAGE="$REGISTRY/search-api:$SOURCE_SHA-$RUN_ID-$RUN_ATTEMPT"
if test -f /etc/lab-ca/root.pem; then
  set -- --secret id=lab_ca,src=/etc/lab-ca/root.pem
else
  set --
fi
docker buildx build --platform linux/amd64,linux/arm64 \
  "$@" \
  --label "org.opencontainers.image.revision=$SOURCE_SHA" \
  --metadata-file image-metadata.json -t "$IMAGE" --push app
docker run --rm -v "$PWD:/work" -w /work \
  -e SOURCE_SHA -e SOURCE_REPOSITORY -e RUN_ID -e RUN_ATTEMPT -e EVENT_KIND \
  -e REGISTRY -e ARTIFACT_URL -e NEXUS_USER -e NEXUS_PASSWORD \
  "$PYTHON_IMAGE" python ci/release.py
