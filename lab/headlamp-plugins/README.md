# Headlamp KServe plugin

The supplied archive contains the built `@headlamp-k8s/kserve` plugin,
version `0.1.0-dev.0`. Its package metadata declares Apache-2.0 licensing.
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
