using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace GGUFSharp
{
    //[StructLayout(LayoutKind.Explicit)]
    public class GGUFHeader
    {
        //[FieldOffset(0)]
        public uint MagicCode;
        //[FieldOffset(4)]
        public uint Version;

        //[FieldOffset(8)]
        public ulong TensorCount;

        //[FieldOffset(24)]
        public ulong MetaKVCount;
    }
}
