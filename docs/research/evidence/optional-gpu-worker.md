# Optional GPU worker verification

Checked on 2 October 2026, Windows x64, Docker Desktop/WSL2 and the existing
`k3d-relevance-lab` cluster. The RTX 4090 laptop GPU has 16,376 MiB VRAM.

| Check | Observed result |
| --- | --- |
| Image build | Pinned k3s v1.35.8, CUDA 13.0.2 base and NVIDIA toolkit 1.20.1 built successfully |
| Worker join | Additional `relevance-gpu-worker` Ready; all three existing nodes remained Ready |
| GPU discovery | Official NVIDIA device plugin v0.18.2 advertises one `nvidia.com/gpu` |
| Kubernetes visibility | A finite GPU-requesting Pod returned the RTX 4090 and 16,376 MiB; no model loaded |
| Lifecycle | Drain/remove/recreate succeeded with retained volumes and node identity; repeated setup reused the worker |
| Model guards | Eight packaging, mapping, registration and promotion tests passed; scheduling assertion checked separately after addition |
| Static checks | Ruff passed for the worker helper and deployment renderer; C4 DSL validation/export passed |

The final worker image identifier is
`sha256:ae8fab3399ed6210c6c948cfd49ccd41df272467a3a2b9b48068b1e48c033061`.
The device plugin is pinned by digest in the helper. Bootstrap credentials stay
in ignored local state and were not included in the evidence.

Nested WSL discovery initially failed with NVML `Not Supported`. Docker injects
`libdxcore.so` under `/usr/lib/x86_64-linux-gnu`; the worker entrypoint makes it
discoverable under `/usr/lib/wsl/lib`, where NVIDIA's nested WSL discovery looks.
The baked image passed recreation and the Kubernetes visibility check. No driver
libraries are copied into Git or embedded from the workstation in the image.

The existing Windows research evaluation remained running throughout these
checks. Kubernetes cannot account for that external allocation. A checkpointed
pause was requested separately before model qualification.

## Limits and next batch

This demonstrates worker preparation, not CUDA inference or model quality.
The active judge remains the all-abstaining version 1. Linux native and Apple
silicon execution were not tested. Apple silicon omits this optional worker.
The [qualification plan](../../plans/esci-model-qualification.md) owns the next
serving and quality checks. The local deployment SVG was regenerated; visual
inspection is recorded separately from runtime verification.
