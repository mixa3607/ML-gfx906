// gfx906 (Vega20 / MI50, wave64) MMQ config.
//
// Perf-only knobs (nthreads / tile widths) - results are bit-exact vs rdna2,
// which is what upstream routes gfx906 through. Include after mmq-config-rdna2.cuh.
//
// Q8_0: 8 warps (nthreads 512, vs rdna2's 4 = 256), and offer tile widths up to
// J=128 (rdna2 caps its Q8_0 table at 64). The wide tiles are only SELECTED when
// they keep the CUs busy - see the occupancy gate in mul_mat_q_switch_J
// (mmq.cuh), which holds J<=64 for row-sharded (-sm tensor) and MoE shapes and
// lets full-row shapes (1-GPU, -sm layer) take the wider tile.
//
// MXFP4: 8 warps as well - rdna2's table with nthreads overridden, so tile
// widths and layout stay in sync with upstream.
//
// Q4_K/Q5_K/Q6_K: measured on MI50. I=64 halves the accumulator array and the X
// LDS tile, cutting VGPR/scratch and improving Q5_K/Q6_K throughput ~15-35%.
// Q4_K stays at I=128 (I=64 makes it ~53% slower). J=64 only.
static constexpr __host__ __device__ ggml_cuda_mmq_config ggml_cuda_mmq_get_config_gfx906(ggml_type type, int J, bool fallback) {
    if (type == GGML_TYPE_Q8_0 && J >= 8 && J <= 128 && (J % 8) == 0) {
        return ggml_cuda_mmq_config(
            GGML_TYPE_Q8_0, 512, 2, 128, J, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_0, MMQ_ITER_K, false, fallback);
    }
    if (type == GGML_TYPE_MXFP4) {
        const ggml_cuda_mmq_config rdna2 = ggml_cuda_mmq_get_config_rdna2(type, J, fallback);
        if (rdna2.type == GGML_TYPE_COUNT) {
            return rdna2;
        }
        return ggml_cuda_mmq_config(
            rdna2.type, 512, rdna2.occupancy, rdna2.I, rdna2.J, rdna2.sram_layout, rdna2.K_vram, rdna2.stream_k, rdna2.fallback);
    }
    CASE(GGML_TYPE_Q4_K, 256, 2, 128, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, true);
    CASE(GGML_TYPE_Q4_K, 256, 2, 128, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, false);

    CASE(GGML_TYPE_Q5_K, 256, 2, 64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, true);
    CASE(GGML_TYPE_Q5_K, 256, 2, 64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, false);

    CASE(GGML_TYPE_Q6_K, 256, 2, 64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q6_K, MMQ_ITER_K, false, true);
    CASE(GGML_TYPE_Q6_K, 256, 2, 64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q6_K, MMQ_ITER_K, false, false);

    return ggml_cuda_mmq_get_config_rdna2(type, J, fallback);
}
