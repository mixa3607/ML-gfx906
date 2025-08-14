namespace ArkProjects.LlmCalc.Options;

public class LLamaDeviceOptions
{
    public required LLamaDeviceType Type { get; set; }
    public string PciBus { get; set; } = "";

    public required long TotalSizeMb { get; set; }
    public long ReservedMemoryMb { get; set; }

    public double LayersPortion { get; set; } = 0;
    public int Id { get; set; }
}