# CPU48 side story: TP2 and prefill chunk 2048

Two independent modifications of final-four; no new control or combined TP2/chunk2048 arm.
TP2 retains all four GPUs and replaces group-local DRAFT_DEV with global DRAFT_GPU=1,2,3.
The reference is older. Different TP/chunk arithmetic may change answers; no answer-parity test.
No automatic baseline update or statistical-significance claim.

## Primary pooled measurements

| Arm | PP tok/s | vs saved final | TG tok/s | vs saved final | Draft accepted / offered | Peak GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| final-four | 410.83 | — | 35.88 | — | 1299 / 1636 (79.40%) | — |
| tp2 | 248.78 | -39.45% | 25.79 | -28.13% | 1246 / 1586 (78.56%) | 215.07 |
| chunk2048 | 352.54 | -14.19% | 35.08 | -2.23% | 1242 / 1562 (79.51%) | 218.47 |

Peak includes preparation and file cache; there is no equivalent record for saved final-four.

## pooled by prompt length

### Prefill

| PP | saved final-four | tp2 | vs final | chunk2048 | vs final |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 239.27 | 159.16 | -33.48% | 240.24 | +0.40% |
| 4096 | 325.59 | 208.54 | -35.95% | 298.63 | -8.28% |
| 8192 | 391.47 | 235.41 | -39.87% | 340.14 | -13.11% |
| 16384 | 420.62 | 255.47 | -39.26% | 361.35 | -14.09% |
| 32768 | 445.72 | 264.78 | -40.59% | 370.59 | -16.85% |

### Decode

| PP | saved final-four | tp2 | vs final | chunk2048 | vs final |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 35.05 | 25.21 | -28.06% | 35.83 | +2.23% |
| 4096 | 38.10 | 25.54 | -32.96% | 36.89 | -3.17% |
| 8192 | 37.30 | 26.05 | -30.16% | 36.22 | -2.90% |
| 16384 | 34.60 | 26.23 | -24.19% | 33.64 | -2.78% |
| 32768 | 34.64 | 25.92 | -25.16% | 33.12 | -4.37% |

## best-of-two by prompt length

Independent PP/TG maxima of two different prompts, not repeated identical inputs.
PP and TG maxima may come from different requests; IDs are below and in comparison.json.

### Prefill

| PP | saved final-four | tp2 | vs final | chunk2048 | vs final |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 248.99 | 165.78 | -33.42% | 250.52 | +0.61% |
| 4096 | 325.61 | 222.15 | -31.77% | 304.95 | -6.34% |
| 8192 | 395.58 | 243.92 | -38.34% | 340.34 | -13.96% |
| 16384 | 422.44 | 256.26 | -39.34% | 365.47 | -13.49% |
| 32768 | 449.98 | 265.41 | -41.02% | 371.54 | -17.43% |

### Decode

| PP | saved final-four | tp2 | vs final | chunk2048 | vs final |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 35.74 | 25.90 | -27.55% | 36.28 | +1.49% |
| 4096 | 39.84 | 26.77 | -32.80% | 39.47 | -0.92% |
| 8192 | 40.05 | 27.12 | -32.28% | 40.10 | +0.11% |
| 16384 | 35.42 | 26.30 | -25.75% | 34.54 | -2.49% |
| 32768 | 35.34 | 26.16 | -25.98% | 34.59 | -2.14% |

## Best-of-two selection provenance

| Arm | PP | Prefill case ID | Decode case ID |
| --- | ---: | --- | --- |
| final-four | 2048 | measurement-00-pp2048 | measurement-00-pp2048 |
| final-four | 4096 | measurement-06-pp4096 | measurement-01-pp4096 |
| final-four | 8192 | measurement-07-pp8192 | measurement-07-pp8192 |
| final-four | 16384 | measurement-08-pp16384 | measurement-03-pp16384 |
| final-four | 32768 | measurement-04-pp32768 | measurement-09-pp32768 |
| tp2 | 2048 | measurement-00-pp2048 | measurement-05-pp2048 |
| tp2 | 4096 | measurement-01-pp4096 | measurement-01-pp4096 |
| tp2 | 8192 | measurement-02-pp8192 | measurement-07-pp8192 |
| tp2 | 16384 | measurement-08-pp16384 | measurement-03-pp16384 |
| tp2 | 32768 | measurement-04-pp32768 | measurement-09-pp32768 |
| chunk2048 | 2048 | measurement-00-pp2048 | measurement-05-pp2048 |
| chunk2048 | 4096 | measurement-01-pp4096 | measurement-01-pp4096 |
| chunk2048 | 8192 | measurement-07-pp8192 | measurement-07-pp8192 |
| chunk2048 | 16384 | measurement-08-pp16384 | measurement-03-pp16384 |
| chunk2048 | 32768 | measurement-04-pp32768 | measurement-09-pp32768 |
