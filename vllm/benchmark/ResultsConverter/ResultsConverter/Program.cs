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

    results = results
      .OrderBy(x => x.ModelId)
      .ThenBy(x=>x.MetadataImage)
      .ThenBy(x=>x.MetadataWorkload)
      .ThenBy(x=>x.MaxConcurrency)
      .ThenBy(x=>x.TotalInputTokens / x.NumPrompts)
      .ToList();

    var cols = new Dictionary<string, (bool enable, Func<VllmBenchResult, string> provider)>();
    cols["Date"] = (false, r => r.Date);
    cols["Image"] = (true, r => r.MetadataImage);
    cols["Model"] = (true, r => r.ModelId);
    cols["TP/DP/PP"] = (true, r => "0/0/0");
    cols["Prompts"] = (true, r => r.NumPrompts.ToString());
    cols["Threads"] = (true, r => r.MaxConcurrency.ToString());
    cols["Ctx toks"] = (true, r => (r.TotalInputTokens / r.NumPrompts).ToString("0"));
    cols["Gen toks"] = (true, r => r.MetadataWorkload is "embed" ? "-" : (r.TotalOutputTokens / r.NumPrompts).ToString("0"));
    cols["Duration"] = (false, r => TimeSpan.FromSeconds(r.Duration).ToString("hh\\:mm\\:ss"));
    cols["PP t/s"] = (true, r => r.MetadataWorkload is "tg" ? "-" : r.TotalTokenThroughput.ToString("N2"));
    cols["TG t/s"] = (true, r => r.MetadataWorkload is "pp" or "embed" ? "-" : r.OutputThroughput.ToString("N2"));
    cols["Workload"] = (true, r => r.MetadataWorkload ?? "");
    cols["About"] = (true, r => r.MetadataAbout ?? "");

    var table = new MarkdownTable.MarkdownTableBuilder();
    table.WithHeader(cols.Where(x=>x.Value.enable).Select(x=>x.Key).ToArray());
    foreach (var result in results)
    {
        var fields = cols.Where(x=>x.Value.enable).Select(x=>x.Value.provider(result)).ToArray();
        table.WithRow(fields);
    }

    Console.WriteLine(table.ToString());
}
