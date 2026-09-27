# Independent comparison input check

The control comparison path was exercised from this branch against two existing frozen 10k Search APIs: `lab-pr-base-e333d1b0-10k` and `lab-pr-3-86d476d179-10k`. Neither API nor its index was rebuilt for these runs. The branch was not deployed as a new control Pod; the checks ran the branch's comparison code against the current local cluster.

| Check | Selected inputs | Result |
| --- | --- | --- |
| Default result preservation | Query manifest `144c51398442422cb638b6ef0f9df8c890e54afa6f3cad9383fbd1f93ad495fa`; 50 queries | Complete; changed; observation `9d84d627e33d23fb9dfd7bcdc3b6b6f596df15ff7f7a202a4695e0e49700558a` |
| Default synthetic relevance | Same query manifest; judgement manifest `f30d8e10880e774d2987555450d71b3f0186c2736b534238d0a2c90d2373c69d`; 50 queries | Complete; measured; judgement coverage insufficient; report `91f4401282a191b0fcba3b377a174b55788184e7430284c007d04f71e1e65838` |
| Revised result preservation | Independent three-query manifest `b4405fa0bfac0afa000df90419ace4094a83227893db8b256b99f14c33386efe` | Complete; changed; report `bbce8105b443b4f4e89650c9da0f284bd1f3d5e27cd33a46a22abd0480448fda` |
| Offline rescore | Observation from the default relevance run; exact 10k catalogue, query and judgement manifests | Complete; 50 queries; query content SHA-256 `406a1bfb60bb5a3e7b2747151e77b156f85839cdd671a6f09472acd3ad10f298` |

The 10k and 1M source bytes were validated and published under new independent manifests with producer `synthetic-retail-v2`. Their manifest hashes are pinned in [`default_inputs.json`](../../../lab/default_inputs.json). The selector fetched both sets from Floci and checked 50/1,433 and 1,000/20,000 query/judgement rows respectively. Earlier manifests and reports remain unchanged.

Focused tests cover content hashes, catalogue and judgement dependencies, tampered query bytes, comparison records, API ownership and selected-hash forwarding. These runs show contract wiring and API behaviour. They do not establish relevance validity, performance capacity or the Kubernetes control image rollout.
