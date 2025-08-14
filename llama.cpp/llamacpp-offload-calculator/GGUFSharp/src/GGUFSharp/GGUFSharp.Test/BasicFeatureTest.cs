using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;

namespace GGUFSharp.Test
{
    [TestClass]
    [DoNotParallelize]
    public sealed class BasicFeatureTest
    {
        private string GGUFFilePath = @"example.gguf";
        private string[] example_meta =
            {
                "general.architecture:llama",
                "llama.block_count:GGUF_METADATA_VALUE_TYPE_UINT32",
                "answer:GGUF_METADATA_VALUE_TYPE_UINT32",
                "answer_in_float:GGUF_METADATA_VALUE_TYPE_FLOAT32",
                "general.alignment:GGUF_METADATA_VALUE_TYPE_UINT32"
            };
        private string[] example_tensorInfo =
        {
            "tensor1",
            "tensor2",
            "tensor3"
        };
        [TestMethod]
        public void ReadBasicInfo()
        {
            GGUFReader reader = new GGUFReader();
            var f = reader.Read(GGUFFilePath);
            Assert.IsTrue(f.MetaItems.Select(x=>x.ToString()).SequenceEqual(example_meta));
            Assert.IsTrue(f.TensorInfos.Select(x => x.Name).SequenceEqual(example_tensorInfo));
        }
        [TestMethod]
        public void ReadTensorData()
        {
            GGUFReader reader = new GGUFReader();
            var f=reader.Read(GGUFFilePath);
            using var t1=reader.ReadTensorData(f,f.TensorInfos.FirstOrDefault());
            var data = t1.Memory.Slice(0,(int)f.TensorInfos.First().Size);
            var dataF=MemoryMarshal.Cast<byte,float>(data.Span);
            foreach (var item in dataF)
            {
                Assert.AreEqual(item, 100);
            }
        }
        
    }
}
