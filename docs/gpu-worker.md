# Optional NVIDIA worker

Add one GPU worker to the existing local Kubernetes cluster for model serving.
The normal lab nodes remain CPU-only. The calibrated judgement model uses this
worker. On Apple silicon, omit the worker and select the CPU bootstrap judge;
it returns abstentions for missing labels.

The worker requires an x86 Linux Docker engine with NVIDIA GPU passthrough.
The Windows lab uses Docker Desktop with WSL2. This is a separate Docker-managed
k3s agent, joined to the k3d cluster; it is managed by the commands below rather
than by `k3d node` commands.

## Add and inspect

From the repository root, in PowerShell, with the existing lab running:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/gpu_worker.py build
python lab/gpu_worker.py create
python lab/gpu_worker.py status
```

In a separate checkout, set `LAB_STATE_DIR` to the existing lab's `.lab` directory.
On Linux use `export LAB_STATE_DIR=/absolute/path/to/.lab` and the same Python
commands. Linux instructions require a compatible NVIDIA Docker runtime and
have not been verified by this batch.

Expect `node_ready: true` and `allocatable_gpu: "1"`. Startup may take a few
minutes. If either is absent, inspect:

```powershell
docker logs --tail 50 relevance-gpu-worker
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" -n kube-system get pods -l app=relevance-gpu-worker-device-plugin
```

The default worker RAM limit is 28 GB; choose another limit with
`python lab/gpu_worker.py create --memory 28g` before creation. An existing worker
is reused; that option does not resize it. Its NVIDIA runtime is the default only
on this worker. A node label and scheduling restriction keep ordinary lab Pods
off it; generated ESCI candidate manifests explicitly select and tolerate it.

Creating the worker never deploys a model or starts inference. Kubernetes cannot
account for GPU use by Windows research processes. Coordinate a safe pause of
those processes before deploying the candidate, even when Kubernetes reports
one available GPU. Follow [model qualification](esci-model-installation.md#5-qualify-on-a-gpu-before-promotion).

The cluster join token stays in ignored bootstrap state under `.lab/gpu-worker`.
The worker uses separate Docker volumes and existing lab registry mirrors.

## Remove

Stop GPU model clients and remove their InferenceService first. Then run:

```powershell
python lab/gpu_worker.py remove
```

The command drains and removes this worker and its device plugin. It retains
worker volumes and bootstrap state for recreation, and leaves existing nodes
unchanged. The default lab setup does not create the optional worker.

The image follows the [k3d CUDA approach](https://k3d.io/stable/usage/advanced/cuda/)
and [k3s NVIDIA runtime support](https://docs.k3s.io/advanced#nvidia-container-runtime).
It pins the k3s and CUDA base images and NVIDIA toolkit version; driver support
comes from the host.
