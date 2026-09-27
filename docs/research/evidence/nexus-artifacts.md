# Nexus artifact evidence

Measured on the Windows/Docker Desktop lab on 27 September 2026. Nexus 3.96.3 uses PostgreSQL 17.11; both images are pinned by multi-platform manifest digest.

| Check | Result |
| --- | --- |
| Publisher upload and reader read-back | Matching SHA-256 |
| Identical publication retry | Reused existing bytes |
| Different bytes at an existing path | HTTP 409 |
| Reader publication / publisher deletion / publisher administration | HTTP 403 each |
| Anonymous read | HTTP 401 |
| Nexus restart to retained artifact read | 29.750 s, one sample |
| Private digest pull from Kubernetes | Completed finite Job |
| PostgreSQL | Verified server version and active PostgreSQL data store |

The first persistence probe exposed the default 100-connection pool exhausting PostgreSQL. The committed setup uses 20; the repeated full probe passed. A Nexus container replacement also retained the database, accounts and artifacts through its named volumes. Initial idle Nexus memory was about 1.5 GiB; this is not production sizing evidence.

[Setup pins](nexus-artifacts/nexus-setup.json) and [sanitised checks](nexus-artifacts/nexus-verification.json) retain the exact probe digest and statuses. Reproduce with `python lab/verify_nexus.py` after setup; it restarts Nexus and creates a temporary image-pull namespace which it removes.

Native arm64 execution, off-host backup restoration and sustained artifact load remain unmeasured. The C4 local deployment was regenerated and visually inspected. Portable Actions CI is the next batch.
