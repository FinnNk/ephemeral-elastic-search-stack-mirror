# Adaptive evaluation pacing measurements

Eight workers searched a disposable local HTTP API. Each trial made 48 fresh
queries; successful responses took 80 ms. The service rejected excess concurrent
requests with HTTP 503. Three trials ran for each method and capacity schedule.

| Service | Method | Median seconds | Failed queries per trial | Attempts per trial |
| --- | --- | ---: | --- | --- |
| Healthy, capacity 8 | fixed-retry | 0.516 | 0, 0, 0 | 48, 48, 48 |
| Healthy, capacity 8 | adaptive | 0.516 | 0, 0, 0 | 48, 48, 48 |
| Overloaded, capacity 2 | fixed-retry | 1.937 | 14, 13, 12 | 82, 82, 79 |
| Overloaded, capacity 2 | adaptive | 3.891 | 0, 0, 0 | 59, 59, 59 |
| Capacity 2, then 8 after attempt 16 | fixed-retry | 0.890 | 0, 0, 0 | 58, 58, 58 |
| Capacity 2, then 8 after attempt 16 | adaptive | 1.406 | 0, 0, 0 | 54, 54, 54 |

## Decision and limits

Adopt shared pacing for functional captures. It avoided incomplete evaluations
under sustained overload, with fewer failed requests. It is deliberately slower
while protecting an overloaded API; it does not improve measured search latency.
Healthy trials had no pacing waits, retries or errors. These small local trials
cannot establish a statistically significant normal-service speed difference.

The [first survey](evaluation-pacing-conservative.json) increased spacing for
every simultaneous failure. It recovered too slowly. The adopted controller
counts failures individually but increases spacing at most once per 200 ms.
This reduced the initial burst penalty. Recovery halves spacing after eight
successful responses and removes it once below 10 ms.

The recovery schedule is defined by server attempt count, not a fixed wall clock.
Thread scheduling affects its timings. Requests use the same URL but execute
freshly; there is no response cache. A failed capture remains incomplete.

Transport records include attempts, retries, transient and terminal failures,
peak/final spacing and cumulative worker wait. Cumulative wait is summed across
workers and may exceed elapsed time. Response-contract failures remain query
errors even when the HTTP request succeeded. Gatling is unchanged.

## Open-source options

| Component | Assessment for the existing threaded capture Jobs |
| --- | --- |
| [urllib3 Retry](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html) | Bounded transport retries and Retry-After; shared adaptive spacing still needs separate logic |
| [aiolimiter](https://aiolimiter.readthedocs.io/en/stable/) | Fixed asynchronous rate limiting; would require changing the capture execution model |
| [PyrateLimiter](https://github.com/vutran1710/PyrateLimiter) | Fixed rate budgets; overload feedback and recovery still need separate logic |

A small standard-library controller avoids a new dependency or asynchronous
rewrite. Its policy is intentionally visible in one module.

## Reproduce

From the lab repository root, using Python 3.13 and no running lab services:

```sh
python lab/experiments/evaluation-pacing/run.py --output /absolute/path/pacing.json
```

On Windows, supply a Windows output path. The command binds an ephemeral
loopback port, prints the trial records and closes the server after each trial.
The measurements below were run on Windows; Linux/macOS were not measured.

- Python: `3.12.8`.
- Controller SHA-256: `7c83e65cea14a1cf2f2ccca893749465cb20ed3c37389889b922794c14baa7de`.
- Full records: [adopted controller](evaluation-pacing.json).
- No live Kubernetes pacing, cloud performance or Gatling load measurement is claimed.
