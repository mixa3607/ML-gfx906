
// https://github.com/marcolink/MarkdownTable
namespace MarkdownTable
{
    public static class MarkdownTableBuilderExtensions
    {
        public static string ToMardownTableString<T>(this IEnumerable<T> rows)
        {
            var builder = new MarkdownTableBuilder();
            var properties = typeof(T).GetProperties().Where(p => p.PropertyType.IsRenderable()).ToArray();
            var fields = typeof(T).GetFields().Where(f => f.FieldType.IsRenderable()).ToArray();

            builder.WithHeader(properties.Select(p => p.Name).Concat(fields.Select(f => f.Name)).ToArray());

            foreach (var row in rows)
            {
                builder.WithRow(properties.Select(p => p.GetValue(row, null))
                    .Concat(fields.Select(f => f.GetValue(row))).ToArray());
            }

            return builder.ToString();
        }

        private static bool IsRenderable(this Type type)
        {
            return type.IsNumeric()
                   || Type.GetTypeCode(type) == TypeCode.String
                   || Type.GetTypeCode(type) == TypeCode.Boolean;
        }

        private static bool IsNumeric(this Type type)
        {
            switch (Type.GetTypeCode(type))
            {
                case TypeCode.Decimal:
                case TypeCode.Double:
                case TypeCode.Single:
                case TypeCode.Byte:
                case TypeCode.Int16:
                case TypeCode.Int32:
                case TypeCode.Int64:
                case TypeCode.SByte:
                case TypeCode.UInt16:
                case TypeCode.UInt32:
                case TypeCode.UInt64:
                    return true;
                case TypeCode.Object:
                    if (type.IsGenericType && type.GetGenericTypeDefinition() == typeof(Nullable<>))
                    {
                        return Nullable.GetUnderlyingType(type).IsNumeric();
                    }
                    return false;
                default:
                    return false;
            }
        }
    }
}