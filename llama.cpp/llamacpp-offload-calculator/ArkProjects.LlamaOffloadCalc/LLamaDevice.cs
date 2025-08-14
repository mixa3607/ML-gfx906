namespace ArkProjects.LlmCalc;

public class LLamaDevice
{
    public required LLamaDeviceType Type { get; set; }
    public required string Name { get; set; }
    public string PciBus { get; set; } = "";

    public required long TotalSize { get; set; }
    public long ReservedMemory { get; set; }

    public List<TensorMetadata> Tensors { get; set; } = [];
    public List<int> Layers { get; set; } = [];
    public double LayersPortion { get; set; } = 0;

    public long GetUsedSpace() => ReservedMemory + Tensors.Aggregate(0L, (current, tensor) => current + tensor.Size);

    public long GetFreeSpace() => TotalSize - GetUsedSpace();
}