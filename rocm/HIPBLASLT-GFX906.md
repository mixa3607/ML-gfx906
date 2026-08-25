# hipBLASLt and gfx906

## Conclusion

`hipBLASLt` is not usable for gfx906 in the ROCm stacks checked here:

- ROCm 6.3.3 has no `*gfx906*` files in `lib/hipblaslt/library`.
- TheRock ROCm 7.14 builds hipBLASLt only for `gfx1100` and packages no
  `lib/hipblaslt/library/gfx906` payload.
- The current upstream hipBLASLt source excludes gfx906 from its supported
  build targets and has no `vega20` Tensile logic files.

This establishes that official gfx906 device libraries are absent from these
releases. It does not prove that no private or third-party build has ever
existed.

## Why rocBLAS works

`rocBLAS` and `hipBLASLt` are distinct libraries with separate Tensile device
libraries:

| Library | Runtime device-library path | gfx906 status in this build |
| --- | --- | --- |
| rocBLAS | `lib/rocblas/library/gfx906` | Present |
| hipBLASLt | `lib/hipblaslt/library/gfx906` | Absent |

The legacy image build rebuilt `rocBLAS` with the ROCm `Tensile` source and
`--architecture gfx906`. It did not build hipBLASLt. The companion extraction
step copied only files from `lib/rocblas/library`.

- [Legacy rocBLAS + Tensile build](https://github.com/mixa3607/llama.cpp-gfx906/blob/d542bcb0e03799573011fa091925dbe54e74e46e/rocm/rocm.Dockerfile)
- [Legacy rocBLAS device-library extraction](https://github.com/mixa3607/llama.cpp-gfx906/blob/5990a75fa914b150009ac45f5b39409b22150711/rocm-tensile/rocm-tensile.Dockerfile)

Those assets satisfy ordinary GEMM paths that reach rocBLAS. They cannot be
used by hipBLASLt: its Tensile mapping files and code objects are a different
payload.

## Current upstream evidence

The links below are pinned to the revisions used by the TheRock build pod.

- [TheRock forces the target-neutral hipBLASLt subproject to `gfx1100`](https://github.com/ROCm/TheRock/blob/418cd5f63abb7a604bad5874cd7b2e29334e640f/math-libs/BLAS/CMakeLists.txt#L126-L142).
- [hipBLASLt supported architectures omit gfx906](https://github.com/ROCm/rocm-libraries/blob/cd9574023093742434e8c992d13b89ab9a6c1cf8/projects/hipblaslt/cmake/tensilelite_supported_architectures.cmake#L4-L28).
- [The runtime loader still recognizes gfx906](https://github.com/ROCm/rocm-libraries/blob/cd9574023093742434e8c992d13b89ab9a6c1cf8/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L2572-L2594).
- [The loader searches a per-architecture Tensile mapping beside the library](https://github.com/ROCm/rocm-libraries/blob/cd9574023093742434e8c992d13b89ab9a6c1cf8/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L2795-L2817).

The retained gfx906 loader branch is therefore compatibility code, not a
complete supported implementation. Without the corresponding
`hipblaslt/library/gfx906` assets it fails during heuristic selection.

## ComfyUI impact

Comfy Kitchen's `int8_tensorwise` operation calls `torch._int_mm`, which in
this PyTorch ROCm build calls `hipblasLtMatmulAlgoGetHeuristic`. It cannot be
redirected to rocBLAS using a runtime environment variable.

Use non-INT8 weights/quantization to stay on ordinary FP16/BF16 rocBLAS GEMM,
or implement a separate fallback that dequantizes and performs FP16 GEMM.
