# syntax=docker/dockerfile:1
FROM rancher/k3s:v1.35.8-k3s1@sha256:59fe491fd3b73204e499e40b325240d85c42c7189c3ae50150d37b78243f3b32 AS k3s
FROM nvidia/cuda:13.0.2-base-ubuntu24.04@sha256:2ab6381d970b211fb93853796dc6707eb8a72575a375c422b17cf4d8b2641701
ARG TOOLKIT_VERSION=1.20.1-1
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg iproute2 iptables kmod ca-certificates \
    && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
    && curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
       | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' > /etc/apt/sources.list.d/nvidia-container-toolkit.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       nvidia-container-toolkit=${TOOLKIT_VERSION} nvidia-container-toolkit-base=${TOOLKIT_VERSION} \
       libnvidia-container-tools=${TOOLKIT_VERSION} libnvidia-container1=${TOOLKIT_VERSION} \
    && rm -rf /var/lib/apt/lists/*
# Keep Ubuntu's glibc and NVIDIA tools; use the same k3s executable as the CPU nodes.
COPY --from=k3s /bin/k3s /usr/local/bin/k3s
COPY --from=k3s /bin/cni /usr/local/bin/cni
COPY --from=k3s /bin/runc /usr/local/bin/runc
COPY --from=k3s /bin/containerd-shim-runc-v2 /usr/local/bin/containerd-shim-runc-v2
RUN for name in host-local bridge flannel loopback portmap bandwidth firewall tuning; do ln -s cni /usr/local/bin/$name; done
RUN for name in containerd ctr crictl kubectl; do ln -s k3s /usr/local/bin/$name; done
ENV PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
COPY --chmod=755 entrypoint.sh /usr/local/bin/gpu-worker-entrypoint
ENTRYPOINT ["/usr/local/bin/gpu-worker-entrypoint"]
CMD ["agent"]
