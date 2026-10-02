#!/bin/sh
set -eu
# Docker Desktop injects dxcore here; NVIDIA's nested WSL discovery searches
# /usr/lib/wsl/lib. Resolve the host library at startup, not in the built image.
if [ -c /dev/dxg ] && [ -f /usr/lib/x86_64-linux-gnu/libdxcore.so ]; then
    mkdir -p /usr/lib/wsl/lib
    ln -sf /usr/lib/x86_64-linux-gnu/libdxcore.so /usr/lib/wsl/lib/libdxcore.so
fi
exec k3s "$@"
