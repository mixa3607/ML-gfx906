using GGUFSharp;

namespace ArkProjects.LlmCalc;

public class TensorMetadata
{
    public TensorMetadata(GGUFTensorInfo tensorInfo)
    {
        TensorInfo = tensorInfo;
        if (Name.StartsWith("blk"))
            BlkId = int.Parse(Name.Split(".").Skip(1).First());
    }

    public GGUFTensorInfo TensorInfo { get; }
    public string Name => TensorInfo.Name;
    public long Size => (long)TensorInfo.Size;
    public int BlkId { get; } = -1;
}