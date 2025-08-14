namespace ArkProjects.LlmCalc.Options;

public class TensorsOffloadRuleOptions
{
    public required string Regex { get; set; }
    public int Id { get; set; }
    public int Priority { get; set; }
}