# Frozen judgement inputs for fresh installation

These compressed rows reproduce the judgement manifests selected by
`lab/default_inputs.json`. The installer checks the original manifest and
uncompressed content hashes before publishing them to new Blob storage.

The full ESCI snapshot contains 24,088 rows: published assessments and the
previously accepted temporary lab demo predictions. Every row retains its
source and eligibility metadata. Predictions remain distinguishable from
independent ground truth; they do not qualify a model. The demo subset contains
981 published assessments. Source notices are in `data/notices`.

The archive contains no model weights, credentials, certificates or CA keys.
It is approximately 0.8 MB compressed. Catalogue bytes are downloaded separately
from the locked upstream sources. See `docs/fresh-install.md` for installation
and `docs/judgement-resolution.md` for judgement provenance.
