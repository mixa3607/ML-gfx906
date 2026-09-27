# Benchmark results

`format-bench-results.py` converts one llama-bench JSONL file into a configured
report. Requires Python 3.10+ and PyYAML.

## Usage

From this directory:

```bash
python3 format-bench-results.py bench-sample-output.jsonl --format md-table
python3 format-bench-results.py bench-sample-output.jsonl --format json > report.json
python3 format-bench-results.py bench-sample-output.jsonl --format yaml > report.yaml
```

`--format yaml|json|md-table` is required. Output goes to stdout. `--config PATH`
selects the column configuration; by default the script uses
`result-format.yaml` next to itself, independently of the working directory.
`--version` prints the generator version.

Use `--no-header` with `--format md-table` to output only data rows, without the
heading or separator row. It has no effect on JSON or YAML output.

Use repeatable `--add-column KEY=VALUE` arguments to append metadata to every row:

```bash
python3 format-bench-results.py results.jsonl --format md-table \
  --add-column rocm-version=7.14 --add-column image=aaaa
```

Columns already listed in the configuration keep their position and heading;
their CLI values bypass transformations. New columns appear after configured
columns, in CLI order, and use their IDs as Markdown headings.
Values remain literal strings in every output format
(for example, `7.10` stays `"7.10"`). Only the first `=` separates the key from
the value; `key=` supplies an empty string. Quote the whole argument when it
contains spaces. A collision with a field in any input JSONL record is an error,
even if that field is null or not selected in the configuration. Listing the
column in the configuration is not a collision. Repeated CLI keys use the last
value. Keys must be non-empty.

Input must contain one JSON object per non-empty line, without benchmark logs
mixed in. Blank lines are ignored. Invalid input reports the filename and line
number and exits unsuccessfully before printing a report.

Each input record produces one output row, in input order. Records are not
grouped, sorted, or aggregated; prompt processing and generation measurements
remain separate.

## Column configuration

```yaml
version: 1
columns:
  model:
    field: model_type
    name: Model
  avg_ts:
    name: Avg tok/s
    precision: 2
  flash_attn:
    name: Flash attention
    format: map
    map:
      -1: auto
      0: "off"
      1: "on"
```

Columns appear in configuration order. The mapping key is the output column ID.

| Option | Meaning |
| --- | --- |
| `field` | Input JSON field; defaults to the column ID |
| `name` | Markdown heading; defaults to the column ID |
| `enabled` | Include the column, default `true` |
| `format` | Transformation, default `raw` |
| `precision` | Decimal places for numeric values; also used by `bytes` |

Supported formats:

- `raw`: preserve the value, optionally rounding numbers using `precision`.
- `map`: look up the input value in the column's `map` mapping. Unknown values
  pass through unchanged. Mapping keys should match the input types: use integer
  keys for numeric enums. Quote YAML strings such as `"on"` and `"off"`.
- `hf-path`: convert a standard Hugging Face cache path
  `models--owner--repo/snapshots/revision/file.gguf` to `owner/repo/file.gguf`,
  preserving subdirectories within the snapshot. Other paths become basenames.
- `bytes`: format a numeric byte count as a string with a unit. `unit` supports
  `B`, `KiB`, `MiB`, `GiB`, and `TiB`; defaults are `GiB` and `precision: 2`.
- `count`: count non-empty pieces of a string separated by `separator` (default
  `/`). For device lists, empty strings and `none` produce `0`; `auto` produces
  a missing value because the actual device count cannot be inferred.

Missing fields and explicit JSON nulls stay missing, including for `map`.
An incompatible input type for a transformation reports the input line and
column. See [result-format.yaml](result-format.yaml) for the complete example.

## Output formats

JSON and YAML produce a list of objects keyed by column ID, not heading. Numbers
stay numeric after rounding; formatting transformations can change the type
(for example, `bytes` produces `"16.02 GiB"`). Missing values are `null`.

Markdown uses `name` for headings and `—` for missing values. Numeric columns
with `precision` display that many decimal places. Pipes and Markdown formatting
characters are escaped; newlines become `<br>` inside cells.

For an empty input, JSON/YAML output an empty list and Markdown outputs the table
header (or nothing with `--no-header`). At least one column must be enabled.
