using System.Text.RegularExpressions;
using GGUFSharp;

namespace ArkProjects.LlmCalc;

public class LLamaGgufMetadataExtractor
{
    private readonly string _ggufModelPath;
    private readonly Regex _nameMatchRegex = new Regex(@"(?<name>^.+)-(?<current>\d{5})-of-(?<total>\d{5}).gguf");

    public LLamaGgufMetadataExtractor(string ggufModelPath)
    {
        _ggufModelPath = ggufModelPath;
    }

    public List<TensorMetadata> ExtractMetadata()
    {
        var reader = new GGUFReader();
        var tensorInfos = new List<TensorMetadata>();
        var fileName = Path.GetFileName(_ggufModelPath);
        var match = _nameMatchRegex.Match(fileName);
        if (!match.Success)
        {
            var file = _ggufModelPath;
            Console.WriteLine($"Reading {file}");
            var f = reader.Read(file);
            tensorInfos.AddRange(f.TensorInfos.Select(t => new TensorMetadata(t)));
        }
        else
        {
            var totalParts = int.Parse(match.Groups["total"].Value);
            var name = match.Groups["name"].Value;

            for (int i = 1; i <= totalParts; i++)
            {
                var file = Path.Combine(Path.GetDirectoryName(_ggufModelPath)!,
                    $"{name}-{i:D5}-of-{totalParts:D5}.gguf");
                Console.WriteLine($"Reading {file}");
                var f = reader.Read(file);
                tensorInfos.AddRange(f.TensorInfos.Select(t => new TensorMetadata(t)));
            }
        }

        return tensorInfos;
    }
}
