# Keep Nexus reachable after Docker restarts

Docker restarted Nexus at `172.30.0.4` while the cluster EndpointSlice retained
`172.30.0.9`. Build 184's promotion failed before evaluation when reading its
release receipt. The existing network repair restored the route and verified
the receipt and all 19 bundle files.

## Change

Install an idempotent k3d server startup hook through Nexus setup and network
repair. Its background shell watcher resolves the Docker container name every
15 seconds and updates only the lab-owned Nexus EndpointSlice when needed.
It waits for API/DNS startup, checks the resource version before a change and
logs transitions. It uses the node's existing kubeconfig and adds no image,
container, credentials or Docker socket. It never replays delivery operations.

An explicit Docker address was considered first. A disposable stop/start test
showed another container could claim that address while Nexus was stopped.
Address reservation alone was therefore discarded before any live activation.

## Verification and acceptance

Run the installer unit tests and the shell fixture in a disposable container
using the lab's k3s image. Cover DNS/API unavailability, ownership rejection,
concurrent API changes, periodic repair, unchanged routes, duplicate setup and
reused PID files. All three installer unit tests and these shell cases passed
on Windows with the lab's Linux k3s image. The shell fixture used a disposable
container with no network access and fixture DNS/API responses. No real lab
restart or endpoint mutation was performed by these checks.

The dashboard retry repair is the preceding batch. After both batches are
accepted, activate the dashboard repair and run network repair once on this lab.
Verify the installed watcher and current Nexus read without restarting active
work. Native Mac and a complete Docker Desktop restart remain separate checks.
