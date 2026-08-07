static constexpr __host__ __device__ ggml_cuda_mmq_config ggml_cuda_mmq_get_config_gfx906(
        ggml_type type, int J, bool fallback) {
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
