# Repeat the local snapshot research

**Isolated research replay.** The ordinary restore path is in the [index recovery guide](../../docs/index-recovery.md). This recipe creates and removes separate probe resources; its timing results do not establish cloud restore performance.

Run these commands in PowerShell from the repository root after the [platform research bootstrap](../platform-spike/README.md) and both frozen releases are available. The probe uses synthetic data only. It creates a **separate** ECK cluster named `lab-fs-probe` and a local repository PVC; the shared cluster is not reconfigured. Allow approximately 3 GiB of Pod memory and 6 GiB of requested PVC capacity for the probe. Do not apply its manifest over an existing resource of the same name.

1. Check that the temporary names are free, then create the probe:

   ```powershell
   kubectl --kubeconfig .lab/kubeconfig.yaml get elasticsearch lab-fs-probe -n platform --ignore-not-found
   kubectl --kubeconfig .lab/kubeconfig.yaml get pvc lab-fs-snapshot-repo -n platform --ignore-not-found
   kubectl --kubeconfig .lab/kubeconfig.yaml apply -f research/snapshot-restore/fs-probe.yaml
   kubectl --kubeconfig .lab/kubeconfig.yaml get elasticsearch lab-fs-probe -n platform
   ```

   Wait for `HEALTH=green` and `PHASE=Ready`. The PVC mounted at `/mnt/snapshots` is the filesystem repository; it survives an Elasticsearch Pod restart but remains local to the lab's k3d storage.

2. Run both source-index snapshots and three restores per size:

   ```powershell
   $env:PYTHONPATH = '.lab/python-libs;lab;research/platform-spike;research/snapshot-restore'
   python research/snapshot-restore/probe_fs.py --release retail-gb-10k-v1 --trials 3
   python research/snapshot-restore/probe_fs.py --release retail-gb-1m-v1 --trials 3
   ```

   Each run verifies the repository, builds its own source index, takes a regular snapshot, **deletes the source**, restores under another name and checks the count, recipe marker, write block and ordered sample. It deletes the restored index after every trial. The million-product initial bulk load uses a local port forward, so do not treat its build duration as the normal in-cluster Job result. Results are saved under ignored `.lab/evidence/fs-snapshot-10k.json` and `.lab/evidence/fs-snapshot-1m.json`.

3. Check repository persistence through a Pod restart:

   ```powershell
   kubectl --kubeconfig .lab/kubeconfig.yaml delete pod lab-fs-probe-es-lab-0 -n platform --wait=true
   python research/snapshot-restore/verify_after_restart.py
   ```

   The verifier waits for the cluster, restores the million-product snapshot without the source index, checks its ordered sample against the frozen product object, and deletes its restored index. Its local result is `.lab/evidence/fs-snapshot-after-restart.json`.

4. Remove the temporary cluster and repository after the checks:

   ```powershell
   kubectl --kubeconfig .lab/kubeconfig.yaml delete elasticsearch lab-fs-probe -n platform --wait=true
   kubectl --kubeconfig .lab/kubeconfig.yaml wait --for=delete pod/lab-fs-probe-es-lab-0 -n platform --timeout=180s
   kubectl --kubeconfig .lab/kubeconfig.yaml delete pvc lab-fs-snapshot-repo -n platform --ignore-not-found
   ```

   ECK deletes the probe's data PVC with its Elasticsearch resource. The command above removes the separate repository PVC, so its snapshots do not persist after cleanup. Keep the recorded results before running it.

To measure a no-reindex option that still depends on a live source index, run `python lab/probe_index_clone.py` with the shared million-product index present. It creates and removes one named target per trial. Check that `lab-clone-probe-1m` does not already exist before starting. [Results and limits](../../docs/research/index-restoration-options.md).
