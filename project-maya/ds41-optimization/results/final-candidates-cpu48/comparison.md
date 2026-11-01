# CPU48 six-flag candidates with and without HC mix/split

Exactly two new runs, no fresh control. Control/four rows are earlier saved measurements.
No automatic baseline change or statistical-significance claim.

## Primary pooled measurements

| Arm | PP tok/s | vs saved control | TG tok/s | vs saved control | Accepted / offered | Pod memory peak GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344.69 | — | 35.06 | — | 1284 / 1618 (79.36%) | — |
| four | 410.83 | +19.19% | 35.88 | +2.34% | 1299 / 1636 (79.40%) | — |
| six | 381.26 | +10.61% | 35.29 | +0.67% | 1288 / 1739 (74.07%) | 218.87 |
| six-hc-mix | 404.12 | +17.24% | 34.77 | -0.81% | 1266 / 1720 (73.60%) | 218.66 |

HC mix added (second vs first): PP +5.99%, TG -1.47%.

Pod memory peak includes preparation and file cache; old references have no equivalent record.

## pooled by prompt length

### Prefill

| PP | saved control | saved four | six | six-hc-mix | HC mix vs six |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 132.09 | 239.27 | 240.25 | 228.70 | -4.81% |
| 4096 | 212.71 | 325.59 | 312.55 | 290.17 | -7.16% |
| 8192 | 301.60 | 391.47 | 384.56 | 360.10 | -6.36% |
| 16384 | 368.38 | 420.62 | 395.95 | 426.57 | +7.73% |
| 32768 | 421.24 | 445.72 | 398.59 | 449.66 | +12.81% |

### Decode

| PP | saved control | saved four | six | six-hc-mix | HC mix vs six |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 33.97 | 35.05 | 35.54 | 32.74 | -7.89% |
| 4096 | 36.03 | 38.10 | 36.43 | 34.64 | -4.93% |
| 8192 | 35.83 | 37.30 | 37.28 | 36.82 | -1.23% |
| 16384 | 35.64 | 34.60 | 33.10 | 36.36 | +9.86% |
| 32768 | 33.94 | 34.64 | 34.41 | 33.65 | -2.21% |

## best-of-two by prompt length

Independent PP/TG maxima from two different prompts, not repeated identical inputs.
Selected case IDs are retained in comparison.json; maxima need not be the same request.

### Prefill

| PP | saved control | saved four | six | six-hc-mix | HC mix vs six |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 137.74 | 248.99 | 253.67 | 233.35 | -8.01% |
| 4096 | 220.58 | 325.61 | 326.92 | 304.57 | -6.83% |
| 8192 | 304.86 | 395.58 | 389.10 | 375.75 | -3.43% |
| 16384 | 369.14 | 422.44 | 410.43 | 427.96 | +4.27% |
| 32768 | 423.67 | 449.98 | 420.78 | 454.97 | +8.12% |

### Decode

| PP | saved control | saved four | six | six-hc-mix | HC mix vs six |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 35.40 | 35.74 | 35.80 | 35.05 | -2.07% |
| 4096 | 39.17 | 39.84 | 38.09 | 35.19 | -7.61% |
| 8192 | 38.77 | 40.05 | 39.57 | 38.14 | -3.62% |
| 16384 | 36.71 | 35.42 | 34.62 | 38.31 | +10.66% |
| 32768 | 34.61 | 35.34 | 36.02 | 33.74 | -6.34% |
