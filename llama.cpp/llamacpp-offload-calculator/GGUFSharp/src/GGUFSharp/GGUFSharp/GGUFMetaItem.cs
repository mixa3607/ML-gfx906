using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace GGUFSharp
{
    public   class GGUFMetaItem
    {
        public GGUFDataTypeEnum DataType { get; set; }
        public GGUFDataTypeEnum? ArrayElementType { get; set; }
        public string Name { get; set; }
        public byte[] RawData { get; set; }
        public string[] ArrayStrings { get; set; }
        public override string ToString()
        {
            StringBuilder sb = new StringBuilder($"{Name}:");
            switch(DataType)
            {
                case GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING:
                    sb.Append(Encoding.UTF8.GetString(RawData));
                    break;
                case GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_ARRAY:
                    if (ArrayElementType==GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING)
                    {
                        if (ArrayStrings.Length>10)
                        {
                            sb.Append($"{string.Join(", ", ArrayStrings.Take(10))}...");
                        }
                        else
                        {
                            sb.Append(string.Join(", ", ArrayStrings));
                        }
                    }
                    else
                    {
                        sb.Append($"[{Enum.GetName(typeof(GGUFDataTypeEnum), ArrayElementType)}]");
                    }
                    break;
                default:
                    sb.Append(Enum.GetName(typeof(GGUFDataTypeEnum), DataType));
                    break;
            };
            return sb.ToString();
        }
    }
}
