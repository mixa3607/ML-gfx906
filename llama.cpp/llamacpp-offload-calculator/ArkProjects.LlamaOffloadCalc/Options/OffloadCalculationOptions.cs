namespace ArkProjects.LlmCalc.Options;

public class OffloadCalculationOptions
{
    public bool PrintTensorsSize { get; set; } = false;
    public bool PrintHelmCharConfig { get; set; } = false;
    public bool PrintCmdConfig { get; set; } = false;
    public required string GgufFile { get; set; }
    public required Dictionary<string, LLamaDeviceOptions> Devices { get; set; }
    public required Dictionary<string, TensorsOffloadRuleOptions> OffloadRules { get; set; }
}