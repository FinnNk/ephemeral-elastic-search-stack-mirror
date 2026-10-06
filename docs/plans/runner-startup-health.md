# Runner startup recovery

Restore queued source checks after a lab restart and prevent a running Docker
process from hiding a runner that has not started.

## Scope and constraints

- Keep runner images, labels, registration, capacity and retained volumes.
- Restart only an idle runner; preserve the queued source commit.
- Use Kubernetes startup checks with a five-minute allowance and daemon readiness.
- Repair the existing Nexus route from its actual Docker address.
- Keep Gitea connectivity separate from local process readiness.

## Acceptance

- Both Gitea runners report online.
- The queued release workflow runs for its original commit.
- Runner probe commands succeed against the installed image.
- Kubernetes accepts both manifests and a guarded runner starts successfully.
- Nexus route repair succeeds twice and leaves repositories/accounts untouched.

## Next batch: resume report review

Both runner deployments now use the probes; their restarts were verified while idle.
After acceptance, Open source PR #31 and inspect its fresh comparison: gate status, baseline/variant
nDCG, matching scores and the additional sneakers suite. Keep this developer
workflow free of kubectl. Follow [remote delivery](../remote-delivery.md) and
[Nexus recovery](../nexus.md) for operator-only recovery.
