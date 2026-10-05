# Build script commands

Scripts using `build-common.sh` expose the same interface:

- `check`: print `true` (build needed) or `false` (skip) to stdout; exit 0
  for either result. Diagnostics go to stderr; lookup errors exit nonzero.
- `build`: build and optionally publish without checking the output artifact.
  Required base images are still checked.
- No arguments: check, then build or successfully skip.

To migrate a script, keep artifact identity/configuration outside the callbacks,
move build arguments and execution into `build`, and add:

```bash
source ../.build/build-common.sh

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${PROJECT_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$BASE_IMAGE"
  # Existing build and publication commands.
}

build_dispatch check build "$@"
```

Use `set -eo pipefail`. Call `build_dispatch` directly, not inside `if`, `!`,
`&&` or `||`: Bash disables errexit inside functions called in those contexts.
For non-image artifacts, implement `check` with the same stdout/exit contract.

In CI, resolve versions once and share them through `$GITHUB_ENV`. Capture
`check` into a step output and condition cleanup/build on `needed == 'true'`.
Force-build must be passed to the check step too. A missing dependency fails
before cleanup; a registry/network/authentication error must not mean absent.

Only `llama.cpp-multiruntime` currently uses this interface. Workflows checking
out older release tags need a new release ref before using the new commands.
