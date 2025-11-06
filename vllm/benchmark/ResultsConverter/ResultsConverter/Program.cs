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
    table.WithHeader("date", "rocm",
        //"torch", 
        "vllm",
        //"triton", 
        //"TP", 
        "PwrCap", "Model", "Prompts",
        "Threads",
        "AVG in",
        "AVG out",
        "Duration",
        "RPM",
        "TG",
        "Total TPS",
        "Workload",
        "About");
    foreach (var result in results)
    {
        var ispp = result.MetadataWorkload?.StartsWith("pp;") == true;
        var istg = result.MetadataWorkload?.StartsWith("tg;") == true;

        var fields = new List<string>();
        fields.Add(result.Date);
        fields.Add(result.MetadataRocmVer);
        //fields.Add(result.MetadataTorchVer);
        fields.Add(result.MetadataVllmVer);
        //fields.Add(result.MetadataTritonVer);
        //fields.Add(result.MetadataTensorParallelism);
        fields.Add(result.MetadataPowerCap);
        fields.Add(result.ModelId);
        fields.Add(result.NumPrompts.ToString());
        fields.Add(result.MaxConcurrency.ToString());
        fields.Add((result.TotalInputTokens / result.NumPrompts).ToString("0"));
        fields.Add((result.TotalOutputTokens / result.NumPrompts).ToString("0"));

        fields.Add(TimeSpan.FromSeconds(result.Duration).ToString("hh\\:mm\\:ss"));
        fields.Add(ispp || istg ? "-" : (result.RequestThroughput * 60).ToString("N2"));
        fields.Add(ispp ? "-" : result.OutputThroughput.ToString("N2"));
        fields.Add(istg ? "-" : result.TotalTokenThroughput.ToString("N2"));

        fields.Add(ispp ? "pp" : istg ? "tg": (result.MetadataWorkload ?? ""));
        fields.Add(result.MetadataAbout);
        //fields.Add(result.MetadataBenchmarkAuthor);

        table.WithRow(fields.ToArray());
    }

    Console.WriteLine(table.ToString());
}
