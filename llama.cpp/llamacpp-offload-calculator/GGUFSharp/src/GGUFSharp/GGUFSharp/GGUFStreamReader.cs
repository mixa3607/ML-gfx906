using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace GGUFSharp
{
    internal class GGUFStreamReader : BinaryReader
    {
        public GGUFStreamReader(Stream stream) : base(stream)
        {
        }
        
    }
}
