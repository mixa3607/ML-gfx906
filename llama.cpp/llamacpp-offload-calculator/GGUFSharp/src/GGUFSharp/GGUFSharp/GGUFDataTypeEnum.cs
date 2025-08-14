using System;
using System.Collections.Generic;
using System.Text;

namespace GGUFSharp
{
    public enum GGUFDataTypeEnum : uint
    {
        // The value is a 8-bit unsigned integer.
        GGUF_METADATA_VALUE_TYPE_UINT8 = 0,
        // The value is a 8-bit signed integer.
        GGUF_METADATA_VALUE_TYPE_INT8 = 1,
        // The value is a 16-bit unsigned little-endian integer.
        GGUF_METADATA_VALUE_TYPE_UINT16 = 2,
        // The value is a 16-bit signed little-endian integer.
        GGUF_METADATA_VALUE_TYPE_INT16 = 3,
        // The value is a 32-bit unsigned little-endian integer.
        GGUF_METADATA_VALUE_TYPE_UINT32 = 4,
        // The value is a 32-bit signed little-endian integer.
        GGUF_METADATA_VALUE_TYPE_INT32 = 5,
        // The value is a 32-bit IEEE754 floating point number.
        GGUF_METADATA_VALUE_TYPE_FLOAT32 = 6,
        // The value is a boolean.
        // 1-byte value where 0 is false and 1 is true.
        // Anything else is invalid, and should be treated as either the model being invalid or the reader being buggy.
        GGUF_METADATA_VALUE_TYPE_BOOL = 7,
        // The value is a UTF-8 non-null-terminated string, with length prepended.
        GGUF_METADATA_VALUE_TYPE_STRING = 8,
        // The value is an array of other values, with the length and type prepended.
        ///
        // Arrays can be nested, and the length of the array is the number of elements in the array, not the number of bytes.
        GGUF_METADATA_VALUE_TYPE_ARRAY = 9,
        // The value is a 64-bit unsigned little-endian integer.
        GGUF_METADATA_VALUE_TYPE_UINT64 = 10,
        // The value is a 64-bit signed little-endian integer.
        GGUF_METADATA_VALUE_TYPE_INT64 = 11,
        // The value is a 64-bit IEEE754 floating point number.
        GGUF_METADATA_VALUE_TYPE_FLOAT64 = 12,
    }
    public static class GGUFDataTypeEnumHelper
    {
        public static int GetDataTypeSize(this GGUFDataTypeEnum dateType) => dateType switch
        {
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_UINT8 => 1,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_INT8 => 1,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_UINT16 =>2,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_INT16 => 2,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_UINT32 => 4,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_INT32 => 4,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_FLOAT32 => 4,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_BOOL => 1,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_STRING => -1,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_ARRAY => -1,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_UINT64 => 8,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_INT64 => 8,
            GGUFDataTypeEnum.GGUF_METADATA_VALUE_TYPE_FLOAT64 => 8
        };
    }
    

}
