FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /app
COPY judgements/esci/requirements.lock /app/esci-requirements.txt
RUN pip install --no-cache-dir -r /app/esci-requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
# Triton links a host helper against this SDK stub. The NVIDIA runtime supplies
# the real libcuda.so.1; the stub directory must never enter LD_LIBRARY_PATH.
ADD --checksum=sha256:8295c2bb9e5aca9502e3ec26437054b59ea60dce3580181298c07b81f14a30af https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-driver-dev-12-4_12.4.127-1_amd64.deb /tmp/cuda-driver-dev.deb
RUN dpkg-deb -x /tmp/cuda-driver-dev.deb /opt/cuda-driver-dev && rm /tmp/cuda-driver-dev.deb
ENV TRITON_LIBCUDA_PATH=/opt/cuda-driver-dev/usr/local/cuda-12.4/targets/x86_64-linux/lib/stubs
COPY judgements/predictor.py judgements/telemetry.py judgements/fetch_model.py /app/
COPY judgements/esci/__init__.py judgements/esci/contract.py judgements/esci/engine.py \
    judgements/esci/runtime.py judgements/esci/kernels.py judgements/esci/kernel-profile.json judgements/esci/model.py judgements/esci/release.py /app/esci/
COPY judgements/esci/serve.py /app/serve_esci.py
RUN useradd --uid 10001 --create-home judge && chown -R judge:judge /app
USER 10001
ENV HOME=/home/judge TRITON_CACHE_DIR=/home/judge/.triton/cache PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
ENTRYPOINT ["python"]
CMD ["/app/serve_esci.py"]
