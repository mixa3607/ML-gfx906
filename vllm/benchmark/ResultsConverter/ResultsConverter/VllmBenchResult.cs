using System.Text.Json.Serialization;

public partial class VllmBenchResult
{
    [JsonPropertyName("date")]
    public string Date { get; set; }

    [JsonPropertyName("endpoint_type")]
    public string EndpointType { get; set; }

    [JsonPropertyName("label")]
    public object Label { get; set; }

    [JsonPropertyName("model_id")]
    public string ModelId { get; set; }

    [JsonPropertyName("tokenizer_id")]
    public string TokenizerId { get; set; }

    [JsonPropertyName("num_prompts")]
    public long NumPrompts { get; set; }

    [JsonPropertyName("metadata.rocm_ver")]
    public string MetadataRocmVer { get; set; }

    [JsonPropertyName("metadata.torch_ver")]
    public string MetadataTorchVer { get; set; }

    [JsonPropertyName("metadata.vision_ver")]
    public string MetadataVisionVer { get; set; }

    [JsonPropertyName("metadata.vllm_ver")]
    public string MetadataVllmVer { get; set; }

    [JsonPropertyName("metadata.triton_ver")]
    public string MetadataTritonVer { get; set; }

    [JsonPropertyName("metadata.image")]
    public string MetadataImage { get; set; }

    [JsonPropertyName("metadata.tensor_parallelism")]
    public string MetadataTensorParallelism { get; set; }

    [JsonPropertyName("metadata.about")]
    public string MetadataAbout { get; set; }

    [JsonPropertyName("metadata.benchmark_author")]
    public string MetadataBenchmarkAuthor { get; set; }

    [JsonPropertyName("metadata.power_cap")]
    public string MetadataPowerCap { get; set; }

    [JsonPropertyName("metadata.workload")]
    public string? MetadataWorkload { get; set; }

    [JsonPropertyName("request_rate")]
    public string RequestRate { get; set; }

    [JsonPropertyName("burstiness")]
    public double Burstiness { get; set; }

    [JsonPropertyName("max_concurrency")]
    public long MaxConcurrency { get; set; }

    [JsonPropertyName("duration")]
    public double Duration { get; set; }

    [JsonPropertyName("completed")]
    public long Completed { get; set; }

    [JsonPropertyName("total_input_tokens")]
    public long TotalInputTokens { get; set; }

    [JsonPropertyName("total_output_tokens")]
    public long TotalOutputTokens { get; set; }

    [JsonPropertyName("request_throughput")]
    public double RequestThroughput { get; set; }

    [JsonPropertyName("request_goodput")]
    public object RequestGoodput { get; set; }

    [JsonPropertyName("output_throughput")]
    public double OutputThroughput { get; set; }

    [JsonPropertyName("total_token_throughput")]
    public double TotalTokenThroughput { get; set; }

    [JsonPropertyName("input_lens")]
    public long[] InputLens { get; set; }

    [JsonPropertyName("output_lens")]
    public long[] OutputLens { get; set; }

    [JsonPropertyName("ttfts")]
    public double[] Ttfts { get; set; }

    [JsonPropertyName("itls")]
    public double[][] Itls { get; set; }

    [JsonPropertyName("generated_texts")]
    public string[] GeneratedTexts { get; set; }

    [JsonPropertyName("errors")]
    public string[] Errors { get; set; }

    [JsonPropertyName("mean_ttft_ms")]
    public double MeanTtftMs { get; set; }

    [JsonPropertyName("median_ttft_ms")]
    public double MedianTtftMs { get; set; }

    [JsonPropertyName("std_ttft_ms")]
    public double StdTtftMs { get; set; }

    [JsonPropertyName("p99_ttft_ms")]
    public double P99TtftMs { get; set; }

    [JsonPropertyName("mean_tpot_ms")]
    public double MeanTpotMs { get; set; }

    [JsonPropertyName("median_tpot_ms")]
    public double MedianTpotMs { get; set; }

    [JsonPropertyName("std_tpot_ms")]
    public double StdTpotMs { get; set; }

    [JsonPropertyName("p99_tpot_ms")]
    public double P99TpotMs { get; set; }

    [JsonPropertyName("mean_itl_ms")]
    public double MeanItlMs { get; set; }

    [JsonPropertyName("median_itl_ms")]
    public double MedianItlMs { get; set; }

    [JsonPropertyName("std_itl_ms")]
    public double StdItlMs { get; set; }

    [JsonPropertyName("p99_itl_ms")]
    public double P99ItlMs { get; set; }
}