using System;
using System.Buffers;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;

namespace GGUFSharp
{
    public class GGUFReader
    {
        public GGUFFile Read(string filePath)
        {
            using var fs = MemoryMappedFile.CreateFromFile(filePath);
            using var s = fs.CreateViewStream(0, 0, MemoryMappedFileAccess.Read);
            var header = readHeader(s);
            //using var meta = fs.CreateViewStream(24, 100*1024 * 1024, MemoryMappedFileAccess.Read);
            var d = readMetaData(s, header.MetaKVCount).ToList();
            
            //foreach (var item in d)
            //{
            //    Debug.WriteLine($"{item.Name}, {item.ToString()}");
            //}

            var t = readTensorData(s, header.TensorCount).ToList();
            ulong alignment = 32;//TODO: read align from header


            ulong startOffset = (ulong)s.Position +(alignment-((ulong)s.Position % alignment))% alignment;
            var sortedItems = t.OrderBy(x => x.Offset).ToList();
            for (var i = 0; i < sortedItems.Count - 1; i++)
            {
                sortedItems[i].Size = sortedItems[i + 1].Offset - sortedItems[i].Offset;
            }
            var last = sortedItems.Last();
            last.Size = (ulong)new FileInfo(filePath).Length - last.Offset-startOffset;


            //foreach (var item in t)
            //{
            //    Debug.WriteLine($"[Tensor]{item.Name},{item.DimensionCount},{item.TensorType.ToString()},{item.Offset}");
            //}
            return new GGUFFile()
            {
                FilePath = filePath,
                MetaItems = d,
                TensorInfos = sortedItems,
                Version = header.Version,
                DataStartOffset = startOffset,
            };

        }

        public IMemoryOwner<byte> ReadTensorData(GGUFFile file,GGUFTensorInfo tensor)
        {
            using var fs = MemoryMappedFile.CreateFromFile(file.FilePath);
            using var s = fs.CreateViewStream((long)(file.DataStartOffset+tensor.Offset), (long)tensor.Size, MemoryMappedFileAccess.Read);
            if (tensor.Size>int.MaxValue)
            {
                throw new NotSupportedException("Not supoorted by now, tensor size shoud not larger than max value of int32");
            }
            var om = MemoryPool<byte>.Shared.Rent((int)tensor.Size);
            //BinaryReader br=new BinaryReader(s);
            s.Read(om.Memory.Span);
            return om;
        }


        private GGUFHeader readHeader(Stream header)
        {
            using BinaryReader br = new BinaryReader(header, Encoding.UTF8, true);
            GGUFHeader result = new GGUFHeader();
            result.MagicCode = br.ReadUInt32();
            if (result.MagicCode != 0x46554747) // "GGUF" in little-endian bytes order
            {
                throw new InvalidOperationException("Invalid magic code");
            }
            result.Version = br.ReadUInt32();
            result.TensorCount = br.ReadUInt64();
            result.MetaKVCount = br.ReadUInt64();
            return result;
        }

        private IEnumerable<GGUFMetaItem> readMetaData(Stream meta, ulong MetaCount)
        {
            using BinaryReader br = new BinaryReader(meta, Encoding.UTF8, true);
            for (ulong i = 0; i < MetaCount; i++)
            {

                GGUFMetaItem result = new GGUFMetaItem();
                result.Name = readString(br);
                result.DataType = (GGUFDataTypeEnum)br.ReadUInt32();
                int size;
                switch (result.DataType)
                {
                    case GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING:
                        size = (int)br.ReadUInt64();
                        break;
                    case GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_ARRAY:
                        GGUFDataTypeEnum elementType = (GGUFDataTypeEnum)br.ReadUInt32();

                        if (elementType == GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_ARRAY)
                        {
                            throw new NotSupportedException("Nested array is not supported");
                        }
                        ulong elementCount = br.ReadUInt64();
                        if (elementType == GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING)
                        {
                            result.ArrayStrings = new string[elementCount];
                            result.ArrayElementType = GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING;
                            for (ulong j = 0; j < elementCount; j++)
                            {
                                result.ArrayStrings[j] = readString(br);
                            }
                            size = 0;
                        }
                        else
                        {
                            result.ArrayElementType = elementType;
                            size = (elementType.GetDataTypeSize() * (int)elementCount);
                        }

                        break;
                    default:
                        size = result.DataType.GetDataTypeSize();
                        break;
                }
                if (size > 0)
                {
                    result.RawData = br.ReadBytes(size);
                }


                yield return result;
            }

        }
        private IEnumerable<GGUFTensorInfo> readTensorData(Stream stream, ulong tensorCount)
        {
            using BinaryReader br = new BinaryReader(stream, Encoding.UTF8, true);
            for (ulong i = 0; i < tensorCount; i++)
            {
                GGUFTensorInfo result = new GGUFTensorInfo();
                result.Name = readString(br);
                result.DimensionCount = br.ReadUInt32();
                result.Dimensions = readArray<ulong>(br, result.DimensionCount).ToArray();
                result.TensorType = (GGUFTensorType)br.ReadUInt32();
                result.Offset = br.ReadUInt64();
                yield return result;
            }
        }

        private string readString(BinaryReader reader)
        {
            var l = reader.ReadUInt64();
            var x = reader.ReadBytes((int)l);
            return System.Text.Encoding.UTF8.GetString(x);
        }

        private Span<T> readArray<T>(BinaryReader reader, UInt64 elementCount = 0) where T : struct
        {
            if (elementCount == 0)
            {
                elementCount = reader.ReadUInt64();
            }
            int length = Marshal.SizeOf<T>() * (int)elementCount;
            byte[] buffer = new byte[length];
            reader.Read(buffer, 0, length);
            return MemoryMarshal.Cast<byte, T>(buffer);
        }
    }
}
