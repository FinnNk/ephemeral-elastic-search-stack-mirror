# Larger ESCI fitting-pool survey

Measured on 4 October 2026 on the Windows lab host. **None of the six fixed
classifiers adds useful labels at the required precision.** No predictions were
imported or activated; qualified coverage remains 2,946 / 9,915 (29.71%).

## Inputs and separation

| Item | Measured scope |
| --- | --- |
| Source | Published English US ESCI official training rows; canonical frozen lab catalogue text |
| Selection | 1,000 previously unused query groups; deterministic, label-free cap of 25 products per query |
| Selected pool | 16,768 pairs; 16,594 products; E 11,600 / S 3,353 / C 411 / I 1,404 |
| Fitting | 11,749 pairs / 700 whole query groups |
| Calibration | 5,019 pairs / 300 separate groups; E 3,380 / S 1,097 / C 89 / I 453 |
| Development screen | 6,525 pairs / 400 exposed groups, excluded from new fitting |
| Materialisation | 67.05 seconds; selection and inputs frozen before selected labels were opened |
| MiniLM features | 20,307 unique texts; 287.88 seconds on four CPU threads |

The owner's reservations, source hashes and current exclusion metadata were
checked. The historical research exposure guard is inherited from its verified
receipt; this batch did not reopen its sealed row files. Official test and
confirmation references remained untouched. The complete fitting reservation
stays unavailable for future confirmation.

Features exclude identifiers, labels and synthetic price, popularity and stock.
Whole-query partitions and uncertainty use the owner's conservative HTML/NFKC
normalisation, rather than lexical tokenisation. Actual category paths are
present on 82.4% of fitting pairs, usually at four to five levels. Over half lack
a description; title, brand and bullets remain available where published.

## Selected classifier results

Each class needed at least 30 accepted calibration examples and 98% observed
agreement. Unsupported classes abstained. Added labels below exclude pairs
already accepted by the retained Exact-at-0.95 and simple recalibrator comparator.

| Candidate | Fit and score time | Additional development labels | Agreement on additions |
| --- | ---: | ---: | ---: |
| Lexical/category logistic regression | 17.59 s | 0 | — |
| Numeric role histogram classifier | 12.86 s | 21 Exact | 18 / 21 (85.71%) |
| MiniLM cosine logistic regression | 8.41 s | 15 Exact | 14 / 15 (93.33%) |
| MiniLM cosine histogram classifier | 13.08 s | 0 | — |
| MiniLM pair-feature logistic regression | 18.98 s | 0 | — |
| MiniLM pair-feature small neural network | 53.45 s | 0 | — |

All six completed without convergence warnings. No Substitute, Complement or
Irrelevant class passed the calibration screen. The two candidates accepting
extra Exact pairs failed the development precision screen. Their small query
support also leaves some bootstrap intervals unavailable. No actual-gap
projection was justified.

The comparator accepted 1,753 development pairs with 98.57% agreement. Its
recalibrator was fitted on part of that already exposed cohort, so this is a
descriptive comparator, not independent validation. The new six classifiers
used none of those development references for fitting.

## Retrieval-score pilot

A separate 256-pair development probe measured the pinned
[MS MARCO MiniLM crossencoder](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2).
It supplies a passage relevance logit, not an ESCI judgement or confidence.
AUC measures score separation: 0.5 is random ordering and 1 is perfect
separation. It does not measure the accuracy of accepted ESCI labels.

| Fields | Exact vs Irrelevant AUC | Exact vs all other classes AUC |
| --- | ---: | ---: |
| Title, brand and full category | 0.889 | 0.763 |
| The same fields plus catalogue body | 0.902 | 0.756 |

The probe contained 176 Exact, 53 Substitute, five Complement and 22 Irrelevant
pairs. Complement scores were close to Exact scores. These small exposed samples
do not establish classification quality or a category effect. Of 512 field
inputs, 122 exceeded the 256-token limit and were truncated before model input.

Float inference took 40.84 seconds; dynamic int8 took 39.86 seconds. This small
difference does not justify adopting another numerical runtime. Measurements
shared the host with other work and are not isolated hardware benchmarks.

## Decision and evidence

Stop adding complexity to these frozen embedding classifiers. The next distinct
screen is [supervised pair-model adaptation and CPU prompt inference](../../plans/esci-cpu-pair-judges.md).
The research owner's granular-category prompt study remains unmeasured and
separate from these small classifiers.

The [aggregate receipt](esci-fitted-specialists.json) records input, selection,
outcome and artefact hashes. Pair records, references, memberships and weights
remain in ignored `.lab/esci-fitted-specialists/`. Exact fitting-run source is
retained; packaged tools have formatting refinements. The earlier float
retrieval pilot did not freeze its script, so its provenance is limited to the
retained model, field, runtime, input and output records. No confirmation,
serving parity or model-quality qualification is claimed by these screens.
