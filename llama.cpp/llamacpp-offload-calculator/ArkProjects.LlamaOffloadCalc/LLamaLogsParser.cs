using System.Text.RegularExpressions;

namespace ArkProjects.LlmCalc;

public class LLamaLogsParser
{
    private readonly string _filePath;

    public LLamaLogsParser(string filePath)
    {
        _filePath = filePath;
    }

    public Dictionary<string, List<int>> ExtractAssignedLayers()
    {
        var regex = new Regex(@"load_tensors: layer +(?<layer>\d+) assigned to device (?<device>\S+), ");
        var result = new Dictionary<string, List<int>>();

        var start = -1;
        var lines = File.ReadAllLines(_filePath);
        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i];
            var match = regex.Match(line);
            if (start < 0 && match.Success)
            {
                start = i;
            }

            if (match.Success)
            {
                result.TryAdd(match.Groups["device"].Value, new List<int>());
                result[match.Groups["device"].Value].Add(int.Parse(match.Groups["layer"].Value));
            }


            if (start >= 0 && !match.Success)
            {
                break;
            }
        }

        return result;
    }

    public Dictionary<string, List<string>> ExtractAssignedTensors()
    {
        var regex = new Regex(@"tensor (?<tensor>\S+) \(.+\) buffer type overridden to (?<device>\S+)");
        var result = new Dictionary<string, List<string>>();

        var start = -1;
        var lines = File.ReadAllLines(_filePath);
        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i];
            var match = regex.Match(line);
            if (start < 0 && match.Success)
            {
                start = i;
            }

            if (match.Success)
            {
                result.TryAdd(match.Groups["device"].Value, new List<string>());
                result[match.Groups["device"].Value].Add(match.Groups["tensor"].Value);
            }


            if (start >= 0 && !match.Success)
            {
                break;
            }
        }

        return result;
    }
}