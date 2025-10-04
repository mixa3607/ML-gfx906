// See https://aka.ms/new-console-template for more information

using System.CommandLine;
using System.Text.Json;

Console.WriteLine("Hello, World!");
var resultsDirOpt = new Option<string>("--results-dir", "-i")
{
    Required = true,
};

var genTableCommand = new Command("gen-table", "Generate md table from results")
{
    Options = { resultsDirOpt }
};
genTableCommand.SetAction(result => GenerateTable(result.GetRequiredValue(resultsDirOpt)));

var rootCommand = new RootCommand();
rootCommand.Subcommands.Add(genTableCommand);
return rootCommand.Parse(args).Invoke();


static void GenerateTable(string resultsDir)
{
    var results = new List<VllmBenchResult>();
    foreach (var file in Directory.GetFiles(resultsDir, "*.json", SearchOption.TopDirectoryOnly))
    {
        Console.WriteLine($"Reading {file}");
        results.Add(JsonSerializer.Deserialize<VllmBenchResult>(File.ReadAllText(file))!);
    }

    results = results.OrderBy(x => x.Date).ToList();

    var table = new MarkdownTable.MarkdownTableBuilder();
    table.WithHeader("date", "rocm", "torch", "vllm",
        "triton", "TP", "PwrCap", "Model", "Prompts",
        "Threads", "Duration",
        "Output TPS", "Total TPS", "About");
    foreach (var result in results)
    {
        var fields = new List<string>();
        fields.Add(result.Date);
        fields.Add(result.MetadataRocmVer);
        fields.Add(result.MetadataTorchVer);
        fields.Add(result.MetadataVllmVer);
        fields.Add(result.MetadataTritonVer);
        fields.Add(result.MetadataTensorParallelism);
        fields.Add(result.MetadataPowerCap);
        fields.Add(result.ModelId);
        fields.Add(result.NumPrompts.ToString());
        fields.Add(result.MaxConcurrency.ToString());

        fields.Add(TimeSpan.FromSeconds(result.Duration).ToString());
        fields.Add(result.OutputThroughput.ToString("N2"));
        fields.Add(result.TotalTokenThroughput.ToString("N2"));

        fields.Add(result.MetadataAbout);
        //fields.Add(result.MetadataBenchmarkAuthor);

        table.WithRow(fields.ToArray());
    }

    Console.WriteLine(table.ToString());
}
