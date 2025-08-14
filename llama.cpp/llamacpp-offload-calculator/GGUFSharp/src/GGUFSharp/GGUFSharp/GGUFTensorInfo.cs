using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace GGUFSharp
{
    public class GGUFTensorInfo
    {
        public string Name { get; set; }
        public UInt32 DimensionCount { get; set; }
        public UInt64[] Dimensions { get; set; }
        public GGUFTensorType TensorType { get; set; }
        public UInt64 Offset { get; set; }
        public UInt64 Size { get; set; }
        

    }
}
