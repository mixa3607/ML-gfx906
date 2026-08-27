# Vega 20 thermal-status research

## Confirmed behavior

`atitool -thermalstatus` reads 64 RDI temperatures and four individual HBM
stack temperatures on an AMD Vega 20 (MI50). The standard `amdgpu` hwmon API
only exposes `edge`, `junction`, and aggregate `mem`, so it cannot supply the
same data.

The reference binary was opened in IDA from `D:\rocm-metrics\atitool`.
Relevant functions:

- `sub_ABD136` reads an individual RDI temperature.
- `sub_ABD2FC` maps sensor IDs 50--81 to TMON 0, 82--113 to TMON 1, and IDs
  150--153 to HBM stacks 0--3.
- `sub_ABD0E2` converts the 12-bit temperature field.
- `sub_A7E5B6` is `CVega20GraphicsDevice::MMRegRead32`.

RDI logical register indices used by the binary are:

- TMON 0: `0x1660d` through `0x1662c`
- TMON 1: `0x16631` through `0x16650`

The values have a 12-bit temperature field in bits 23:12. The conversion mode
is selected by the Vega 20 thermal-control object; it is either signed
quarter-degrees or `raw * 0.125 - 49`.

## Important restriction

On this MI50, the active `MMRegRead32` mode maps BAR5 through `/dev/mem` and
reads the cached aperture at `byte_index / 4`. The read-only standalone path is
therefore equivalent for RDI. The prior 185--195 C result was a decoding error:
this device uses `((value >> 12) & 0xfff) * 0.125 - 49`, not signed
quarter-degrees.

HBM uses SMN indirect reads through BAR5 registers `0x0e` (index) and `0x0f`
(data). Stack `n` selects SMN offset `0x57148 + n * 0x200000`; the temperature
is the unsigned byte in data bits 23:16. Selecting an HBM register writes the
volatile SMN index register, and the standalone reader restores its previous
value after the four reads.

The binary also contains a secured/fenced fallback that forwards reads to SMU
operations 36 and 37. That fallback is not active for the RDI register range on
this test bench.

## SVI2 telemetry

`atitool -vctfstatus` also exposes voltage and current telemetry. The Vega 20
implementation reads the SVI2 dword range `0x16800` through `0x16808` through
the same BAR5 aperture. The voltage encoding used for the measured SVI2 values
is `1.55 - byte2 * 0.00625` V; the low byte contains an unscaled current code.

Current requires board-specific calibration from AtomBIOS, not a fixed hardware
scale. The SMC DPM table stores the current at raw code `0` and at raw code
`255`, so the recovered formula is
`current = raw_code * (max_current - offset) / 255 + offset`.

The D163 ROM (`274474.rom`, SHA-256
`68d98d779570f4032ed2b988fea0a35baf20ddb7235034569e165507ab7acd93`) has
an Atom master data table at `0x4e7e`; its SMC DPM info table is at `0x9194`
and is revision 4.4. Four `{ uint16_t max_current, int8_t offset }` records
start at table offset `0x1c`:

- GFX: `768 A`, `0 A`; raw `3` gives `9.035294 A`.
- SOC: `100 A`, `0 A`.
- MEM0: `128 A`, `1 A`; its gain is `0.498039 A/code`.
- MEM1: `16 A`, `0 A`; raw `36` gives `2.258824 A`.

The live `atitool` trace exactly matched GFX, MEM0, and MEM1 calibration.
Those values must not be hard-coded for another board; the standalone reader
must parse the owning adapter's Atom table before publishing current telemetry.

On the D163 board, the read-only SVI2 channel map is plane0/channel1 `0x16803`,
plane0/channel0 `0x16804`, plane1/channel0 `0x16805`, and plane1/channel1
`0x16806`. The standalone labels these by their Atom calibration entries
(`GFX`, `SOC`, `MEM0`, `MEM1`) rather than duplicating `atitool`'s ambiguous
current labels.

Requested-voltage reads initialise and poll SVI2 transaction registers, so the
standalone reader deliberately does not access that path. `vega20-rdi --vbios`
parses the AtomBIOS calibration table and combines it with the read-only
measured telemetry registers.

## Thermal policy and gradient

`CVega20ThermalControl::GetThermalSensorReading` (`sub_ABD2FC`) exposes the
additional read-only thermal values printed by `atitool -vctfstatus`:

- thermal policy temperature: `bar[0x1665f] & 0x1ff` C;
- hardware CTF limit: `((bar[0x16602] >> 6) & 0xff) - 49` C;
- TGRADIENT: the hottest TMON 0 RDI minus `TMON_0_RDIL0`.

On the test bench, GDB traced raw values `0x562b` at `0x1665f` and `0x27e1` at
`0x16602`, yielding 43 C thermal policy and 110 C hardware CTF respectively.
The TGRADIENT implementation walks sensor IDs 50--81, which map exactly to the
32 TMON 0 RDI registers; it subtracts sensor ID 50 rather than the global
minimum RDI temperature.

## Test bench observations

- Host: `kube-worker6.arkprojects.lan`
- Devices: four `1002:66a1` Vega 20 / MI50 GPUs at `33:00.0`, `36:00.0`,
  `4d:00.0`, and `50:00.0`.
- `atitool -thermalstatus` successfully returned all 68 temperatures for the
  first adapter.
- `rocm-smi --showtemp` reported only edge, junction, memory, and zero-valued
  HBM stack placeholders.
