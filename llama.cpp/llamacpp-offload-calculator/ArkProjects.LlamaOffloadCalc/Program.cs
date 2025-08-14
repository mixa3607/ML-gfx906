using ArkProjects.LlmCalc;
using ArkProjects.LlmCalc.Options;
using FluentValidation;
using Microsoft.Extensions.Configuration;
using System.Text;
using System.Text.RegularExpressions;


var options = GetOptions(args);
new OffloadCalculationOptionsValidator().ValidateAndThrow(options);

var tensorsOffloadRules = options.OffloadRules
    .Select(x => (rule: x.Value, name: x.Key, regex: new Regex(x.Value.Regex), tensors: new List<TensorMetadata>()))
    .OrderBy(x => x.rule.Id)
    .ToArray();

var devices = options.Devices
    .OrderBy(x => x.Value.Id)
    .Select(x => new LLamaDevice()
    {
        Name = x.Key,
        TotalSize = x.Value.TotalSizeMb * 1024 * 1024,
        ReservedMemory = x.Value.ReservedMemoryMb * 1024 * 1024,
        Type = x.Value.Type,
        LayersPortion = x.Value.LayersPortion,
        PciBus = x.Value.PciBus,
        Layers = new List<int>(),
        Tensors = new List<TensorMetadata>()
    })
    .ToList();
{
    var gpus = devices.Where(x => x.Type == LLamaDeviceType.GPU).ToList();
    if (gpus.Sum(x => x.LayersPortion) == 0)
    {
        var gpuMem = gpus.Sum(x => x.TotalSize);
        foreach (var gpu in gpus)
        {
            gpu.LayersPortion = (double)gpu.TotalSize / gpuMem;
        }
    }
}

var tensorInfos = new LLamaGgufMetadataExtractor(options.GgufFile)
    .ExtractMetadata()
    .Where(x => x.BlkId != -1)
    .OrderBy(x => x.BlkId)
    .ThenBy(x => x.Name)
    .ToList();

// split layers
var assignedLayers = new Dictionary<string, List<int>>();
{
    var layersCount = tensorInfos.Select(x => x.BlkId).Distinct().Count();
    var layerIds = tensorInfos.Select(x => x.BlkId).Distinct().OrderBy(x => x).ToList();
    var s = devices.Where(x => x.LayersPortion > 0).Sum(x => x.LayersPortion);
    foreach (var device in devices.OrderBy(x => x.LayersPortion))
    {
        if (device.LayersPortion <= 0)
            continue;
        var c = (int)(layersCount / s * device.LayersPortion);
        assignedLayers[device.Name] = layerIds.Take(c).ToList();
        layerIds = layerIds.Skip(c).ToList();
    }

    if (layerIds.Count > 0)
    {
        assignedLayers[devices.GroupBy(x => x.LayersPortion).MaxBy(x => x.Key)!.Last().Name].AddRange(layerIds);
    }
}

// split tensors
foreach (var info in tensorInfos)
{
    tensorsOffloadRules.FirstOrDefault(x => x.regex.IsMatch(info.Name)).tensors?.Add(info);
}

// apply layers
{
    foreach (var assignedLayer in assignedLayers)
    {
        var device = devices.First(x => x.Name == assignedLayer.Key);
        device.Layers.AddRange(assignedLayer.Value);
        device.Tensors.AddRange(tensorInfos.Where(x => assignedLayer.Value.Contains(x.BlkId)));
    }

    if (!devices
            .SelectMany(x => x.Tensors)
            .OrderBy(x => x.Name)
            .SequenceEqual(tensorInfos.OrderBy(x => x.Name))
       )
    {
        throw new Exception();
    }
}

// offload tensors
foreach (var device in devices.Where(x => x.Type == LLamaDeviceType.GPU))
{
    var dst = devices.First(x => x.Type == LLamaDeviceType.CPU);
    while (device.GetFreeSpace() < 0)
    {
        var t = tensorsOffloadRules
            .SelectMany(x => x.tensors.Select(y => (x.rule.Priority, y)))
            .OrderByDescending(x => x.Priority)
            .ThenBy(x => x.y.BlkId)
            .ThenBy(x => x.y.Name)
            .Select(x => x.y)
            .First(x => device.Tensors.Contains(x));
        Console.WriteLine($"Move {t.Name,-25} ({t.Size / 1024 / 1024} Mb) from {device.Name} to {dst.Name}");
        device.Tensors.Remove(t);
        dst.Tensors.Add(t);
    }
}


if (options.PrintTensorsSize)
    PrintTensorsSize(tensorInfos);
PrintDevicesUtilization(devices);
PrintTensorsOffloadResult();
if (options.PrintHelmCharConfig)
    PrintHelmChartConfig(devices);
if (options.PrintCmdConfig)
    PrintCmdConfig(devices);


return;

static void PrintDevicesUtilization(IEnumerable<LLamaDevice> devices)
{
    Console.WriteLine("======= Device memory usage");
    foreach (var device in devices)
    {
        Console.WriteLine($"{device.Name,-10} " +
                          $"{device.GetUsedSpace() / 1024 / 1024} Mb of {device.TotalSize / 1024 / 1024} Mb " +
                          $"({device.Tensors.Aggregate(0L, (current, tensor) => current + tensor.Size) / 1024 / 1024})");
    }

    Console.WriteLine();
}

static void PrintHelmChartConfig(IReadOnlyList<LLamaDevice> devices)
{
    Console.WriteLine("======= Helm chart config");
    var sb = new StringBuilder();
    sb.Append("extraEnvVars:\n");
    sb.Append($"  - name: LLAMA_ARG_MAIN_GPU\n" +
              $"    value: '0'\n");
    sb.Append($"  - name: LLAMA_ARG_TENSOR_SPLIT\n" +
              $"    value: '{string.Join(',', devices.Select(x => x.Layers.Count))}'\n");
    sb.Append("\n");

    sb.Append("modelTensorsOverride:\n");
    foreach (var device in devices.Where(x => x.Type != LLamaDeviceType.GPU && x.Tensors.Count > 0))
    {
        sb.Append($"  - name: {device.Name}\n" +
                  $"    tensors:\n");
        foreach (var tensor in device.Tensors)
        {
            sb.Append($"    - {tensor.Name}\n");
        }
    }

    Console.WriteLine(sb);
}

static void PrintCmdConfig(IReadOnlyList<LLamaDevice> devices)
{
    Console.WriteLine("======= CMD config");
    var sb = new StringBuilder();
    sb.Append("--main-gpu 0 ");
    sb.Append($"--tensor-split \"{string.Join(',', devices.Select(x => x.Layers.Count))}\" ");
    devices
        .Where(x => x.Type != LLamaDeviceType.GPU && x.Tensors.Count > 0)
        .Select(x => $"--override-tensor \"({string.Join('|', x.Tensors.Select(t => t.Name))})={x.Name}\" ")
        .ToList()
        .ForEach(x => sb.Append(x));
    Console.WriteLine(sb);
    Console.WriteLine();
}

static void PrintTensorsSize(IEnumerable<TensorMetadata> tensorInfos)
{
    Console.WriteLine("======= Tensors size");
    foreach (var tensorInfo in tensorInfos.OrderBy(x => x.Size))
    {
        Console.WriteLine($"{tensorInfo.Name,-30} {tensorInfo.Size / 1024 / 1024} Mb");
    }
}

void PrintTensorsOffloadResult()
{
    Console.WriteLine("======= Tensors offload result");
    foreach (var t in tensorsOffloadRules)
    {
        var offloadByDevice = devices
            .Select(x => (x.Name, x.Tensors.Count(y => t.tensors.Contains(y))))
            .ToList();
        Console.WriteLine(
            $"Offload {t.name,-24} ({t.rule.Priority}) {(t.tensors.Count - offloadByDevice.Sum(x => x.Item2)).ToString(),-2} " +
            $"({string.Join(", ", offloadByDevice.Select(x => $"{x.Name} = {x.Item2.ToString(),-2}"))}) " +
            $"of {t.tensors.Count}");
    }

    Console.WriteLine();
}

static OffloadCalculationOptions GetOptions(string[] args)
{
    var mapping = new Dictionary<string, string>()
    {
        { "-e", "environment" }
    };
    string? env;
    // stage 0
    {
        var cfgBuilder = new ConfigurationBuilder()
            .AddJsonFile("appsettings.json", true)
            .AddYamlFile("appsettings.yaml", true)
            .AddYamlFile("appsettings.yml", true)
            .AddEnvironmentVariables()
            .AddCommandLine(args, mapping);

        var cfgRoot = cfgBuilder.Build();
        env = cfgRoot["environment"] ?? null;
    }

    // stage 1
    {
        var cfgBuilder = new ConfigurationBuilder()
            .AddJsonFile("appsettings.json", true)
            .AddYamlFile("appsettings.yaml", true)
            .AddYamlFile("appsettings.yml", true);

        if (!string.IsNullOrWhiteSpace(env))
        {
            cfgBuilder
                .AddJsonFile($"appsettings.{env}.json", true)
                .AddYamlFile($"appsettings.{env}.yaml", true)
                .AddYamlFile($"appsettings.{env}.yml", true);
        }

        cfgBuilder
            .AddEnvironmentVariables()
            .AddCommandLine(args, mapping);

        var cfgRoot = cfgBuilder.Build();
        return cfgRoot.Get<OffloadCalculationOptions>()!;
    }
}
