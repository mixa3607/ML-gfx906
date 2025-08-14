using System;
using System.Collections.Generic;
using System.Text;

namespace GGUFSharp
{
    public class GGUFFile
    {
        public string FilePath { get; set; }
        public uint Version { get; set; }

        public ulong DataStartOffset { get; set; }
        public List<GGUFTensorInfo> TensorInfos { get; set; }
        public List<GGUFMetaItem> MetaItems { get; set; }
    }
}
