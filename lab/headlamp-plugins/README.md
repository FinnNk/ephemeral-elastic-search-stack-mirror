# Headlamp plugins

## KServe plugin

The supplied archive contains the built `@headlamp-k8s/kserve` plugin,
version `0.1.0-dev.29`. Its package metadata declares Apache-2.0 licensing.
The archive is retained unchanged; source code and a separate licence file
were not included in the supplied package.

`lab/headlamp_plugin.py` checks the archive checksum and mounts its JavaScript,
metadata and translations through a Kubernetes ConfigMap. Headlamp loads them
from `/headlamp/plugins/headlamp-kserve`. No build tools or additional service
account permissions are needed in the running Pod.

For an update, replace the archive, update its pinned checksum and package
version checks, then run `python lab/install_headlamp.py install` from the lab
repository with `LAB_STATE_DIR` set. Verify `/plugins` lists `headlamp-kserve`
and refresh the browser to load the new files.

## Custom Prometheus plugin

The [custom release](https://github.com/FinnNk/plugins/releases/tag/prometheus-0.9.1-kserve.1)
contains `prometheus` version `0.9.1-kserve.1`, based on upstream Prometheus
0.9.1 with KServe charts. It is an unofficial test release. The original archive
is retained unchanged and checked against its published SHA-256.

The installer mounts it at `/headlamp/static-plugins/prometheus`, replacing
Headlamp's bundled Prometheus plugin. It must not also be installed in the user
plugins folder: both versions have the same name. No extra RBAC is granted.

Refresh Headlamp after installation. In the Prometheus plugin settings, enable
metrics for `relevance-lab`. If discovery fails, use
`monitoring/kube-prometheus-stack-prometheus:9090` as the Prometheus address.
The testbed's `kserve-test` predictors are scraped for request and latency
metrics; resource charts use the existing CPU and memory metrics. Other
predictors need their own matching scrape configuration and metric contract.

Installation checks verify readiness, one Prometheus discovery entry and every
served asset. They do not establish that charts render in a signed-in browser.
See the [installation evidence](../../docs/research/evidence/headlamp-prometheus-kserve.json).
