# Opt-in v1.1.22 experiments

These patches are not applied by default. Select one through `MAYA_EXPERIMENT`
when building the pinned v1.1.22 source. The image records the selection and
patch SHA256 in `SOURCE_EXPERIMENT.json` and `build-hip/MAYA-BUILD.json`.

- `pr297`: upstream PR #297, commit
  `ce9a6976eaa9f7d156dac2121b4263da734ac582`, rebased onto v1.1.22.
  Conflict resolutions retain both the existing prefill counters and the new
  transfer-pruning counters, includes and test registrations. Runtime opt-in:
  `DS4_SKIP_UNPICKED=1`; no routed expert computation is skipped.
- `pr377`: upstream PR #377, commit
  `2b728d504297ac95f78483bd9eabd1da9c42ddcd`. Corrects TP RAM-copy row ranges
  in the flow path. Do not enable `DS4_FLOW_TP=1` without this fix.
- `pr377-360`: PR #377 plus PR #360, commit
  `db703e9e84f4bf01431ea85aeda77e2ca918fd4c`, pumping flow copies while routing
  is in flight. Runtime control: `DS4_FLOW_PUMP_WAIT=0/1`.

PR #297 operates on the batch path; the other two variants operate on flow.
They are deliberately separate, not a cumulative optimization stack.
All require GPU and full-model numerical validation on gfx906; upstream
performance claims are not measurements of this build or hardware.
