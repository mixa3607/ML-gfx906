# CPU48 combinations and recorded single-flag results

No fresh control was run. Control and single-flag rows come from the preceding block.
Differences may include drift between blocks; no performance verdict or baseline change is applied.

| Arm | PP tok/s | vs saved control | TG tok/s | vs saved control | Accepted / offered |
| --- | ---: | ---: | ---: | ---: | ---: |
| control | 344.69 | — | 35.06 | — | 1284 / 1618 (79.36%) |
| skip | 396.81 | +15.12% | 34.78 | -0.79% | 1278 / 1638 (78.02%) |
| swizzle | 357.81 | +3.80% | 35.34 | +0.81% | 1279 / 1554 (82.30%) |
| hcfuse | 350.81 | +1.77% | 37.05 | +5.69% | 1314 / 1599 (82.18%) |
| routefuse | 353.32 | +2.50% | 35.32 | +0.75% | 1251 / 1605 (77.94%) |
| skip-swizzle | 401.29 | +16.42% | 35.57 | +1.46% | 1340 / 1682 (79.67%) |
| hc-route | 357.52 | +3.72% | 36.49 | +4.09% | 1284 / 1600 (80.25%) |
| all | 410.83 | +19.19% | 35.88 | +2.34% | 1299 / 1636 (79.40%) |

## Combinations versus constituent single-flag runs

| Combination | Compared with | PP delta | TG delta |
| --- | --- | ---: | ---: |
| skip-swizzle | skip | +1.13% | +2.27% |
| skip-swizzle | swizzle | +12.15% | +0.64% |
| hc-route | hcfuse | +1.91% | -1.52% |
| hc-route | routefuse | +1.19% | +3.31% |
| all | skip | +3.53% | +3.16% |
| all | swizzle | +14.82% | +1.52% |
| all | hcfuse | +17.11% | -3.17% |
| all | routefuse | +16.28% | +1.58% |

## All four versus each pair

| Pair | PP delta | TG delta |
| --- | ---: | ---: |
| skip-swizzle | +2.38% | +0.87% |
| hc-route | +14.91% | -1.68% |

## Prefill by prompt length

| PP | saved control | skip-swizzle | Δ | hc-route | Δ | all | Δ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 132.09 | 233.30 | +76.62% | 146.02 | +10.54% | 239.27 | +81.14% |
| 4096 | 212.71 | 272.70 | +28.20% | 239.88 | +12.77% | 325.59 | +53.07% |
| 8192 | 301.60 | 373.71 | +23.91% | 317.46 | +5.26% | 391.47 | +29.80% |
| 16384 | 368.38 | 423.41 | +14.94% | 384.91 | +4.49% | 420.62 | +14.18% |
| 32768 | 421.24 | 444.04 | +5.41% | 419.51 | -0.41% | 445.72 | +5.81% |

## Decode by prompt length

| PP | saved control | skip-swizzle | Δ | hc-route | Δ | all | Δ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 33.97 | 35.51 | +4.51% | 36.27 | +6.76% | 35.05 | +3.17% |
| 4096 | 36.03 | 37.00 | +2.70% | 38.89 | +7.94% | 38.10 | +5.75% |
| 8192 | 35.83 | 35.50 | -0.93% | 37.13 | +3.62% | 37.30 | +4.11% |
| 16384 | 35.64 | 35.13 | -1.42% | 34.54 | -3.08% | 34.60 | -2.91% |
| 32768 | 33.94 | 34.78 | +2.47% | 35.91 | +5.79% | 34.64 | +2.05% |
