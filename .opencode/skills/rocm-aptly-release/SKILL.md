---
name: rocm-aptly-release
description: "Use when processing a pushed tag's Debian artifacts into the ROCm gfx906 aptly repository, creating a snapshot, or publishing it. Requires explicit user approval immediately before any aptly publish operation."
---

# ROCm gfx906 aptly release

Use this procedure after a new Git tag triggers the Debian GitHub Actions in
`mixa3607/ML-gfx906`. The package repository is operated manually through
`kubectl`:

- Namespace: `rocm-build`
- Pod: `aptly-0`
- Incoming package staging: `/root/packages` on PVC `deb-packages`
- Aptly state: `/root/.aptly` on NFS PVC `aptly-data`
- Local aptly repository: `rocm-gfx906`
- Published target: `s3:s3-gfx906:ubuntu`, distribution `noble`, component `main`, architecture `amd64`

## Mandatory publishing gate

**Never run `aptly publish snapshot`, `aptly publish switch`, `aptly publish
drop`, or any other command that changes a published repository unless the
user explicitly approves publishing in the current conversation.**

Creating and inspecting a snapshot does not publish it. After the snapshot is
ready, report its name, package count, and target, then ask for confirmation
to publish that exact snapshot. Do not treat a prior release, a general
request to handle packages, or approval to create a snapshot as publication
approval.

Never display or copy values from `/root/.aptly.conf`, Kubernetes Secrets, or
GPG private-key material. Use the already configured endpoint and the sole
GPG signing key in the pod.

## Snapshot naming

For a normal release, the snapshot name is exactly the Git tag, for example
`20260826041541`.

For an additional non-release update made after that tag, keep the tag as the
base name and append the first unused numeric suffix: `20260826041541-1`,
then `20260826041541-2`, and so on. Never overwrite or delete an existing
snapshot to reuse its name.

## Procedure

### 1. Identify the release and wait for builds

1. Determine the newest pushed tag and its commit:

   ```bash
   git fetch --tags origin
   git tag --sort=-creatordate | head -1
   git show --no-patch --format='%D%n%H%n%cs%n%s' <tag>
   ```

2. List GitHub Actions for that tag and ensure every relevant Debian build is
   `completed` with conclusion `success` before downloading anything:

   ```bash
   gh run list --repo mixa3607/ML-gfx906 --branch <tag> --limit 20 \
     --json databaseId,workflowName,status,conclusion,headBranch,url
   ```

3. For an in-progress build, wait for its run to complete successfully:

   ```bash
   gh run watch <run-id> --repo mixa3607/ML-gfx906 --exit-status
   ```

### 2. Download and validate artifacts

1. Download each successful DEB workflow artifact into a temporary directory
   outside the repository, such as `/tmp/opencode/deb-<tag>`:

   ```bash
   mkdir -p /tmp/opencode/deb-<tag>
   gh run download <run-id> --repo mixa3607/ML-gfx906 \
     --dir /tmp/opencode/deb-<tag>
   ```

2. Find the `.deb` files. Some artifacts contain duplicate copies of the same
   package; select one copy of each package, not both.

3. Validate every selected file before copying it. The package version must
   contain the release tag and the architecture must be `amd64`:

   ```bash
   dpkg-deb -f <package.deb> Package Version Architecture
   sha256sum <package.deb>
   ```

### 3. Stage only new packages in the pod

Inspect the existing staging directories first:

```bash
kubectl exec -n rocm-build aptly-0 -- ls -la /root/packages
```

Use these destinations for the current package workflows:

| Package | Destination |
| --- | --- |
| `amd-tuning` | `/root/packages/amd-tuning` |
| `amd-memory-tweak` | `/root/packages/amd-memory-tweak` |
| `amdrocm7.14-transferbench` | `/root/packages/rocm-transfer-bench` |
| `rocm-validation-suite` | `/root/packages/rocm-validation-suite` |

Create a missing destination and copy only the selected new package. Do not
recopy old package versions or use a wildcard that copies the whole artifact:

```bash
kubectl exec -n rocm-build aptly-0 -- mkdir -p /root/packages/<directory>
kubectl cp <local-package.deb> \
  rocm-build/aptly-0:/root/packages/<directory>/<package-file.deb>
```

Verify the transferred checksum against the local source:

```bash
kubectl exec -n rocm-build aptly-0 -- sha256sum \
  /root/packages/<directory>/<package-file.deb>
```

### 4. Import only the new package files

Check that the intended snapshot name does not already exist:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly snapshot show <snapshot-name>
```

If it exists, stop and select the required `-1`, `-2`, ... suffix. Do not
modify an existing snapshot.

Import only the explicit paths copied for this release. Do not pass a whole
staging directory, as it also contains older package versions:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly repo add rocm-gfx906 \
  /root/packages/amd-tuning/<new-package.deb> \
  /root/packages/amd-memory-tweak/<new-package.deb> \
  /root/packages/rocm-transfer-bench/<new-package.deb> \
  /root/packages/rocm-validation-suite/<new-package.deb>
```

If a workflow did not produce one of these packages, omit its path rather
than substituting an old package.

### 5. Create and verify the snapshot

Create the immutable snapshot from the updated local repository:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly snapshot create <snapshot-name> \
  from repo rocm-gfx906
```

Verify the local repo, snapshot, and package count:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly repo show rocm-gfx906
kubectl exec -n rocm-build aptly-0 -- aptly snapshot show <snapshot-name>
```

At this point stop and ask the user: `Publish snapshot <snapshot-name> to
s3:s3-gfx906:ubuntu/noble?` Do not publish until they answer affirmatively.

### 6. Publish only after explicit approval

After explicit approval for the exact snapshot, switch the published
repository. The pod has one configured signing key, so use it rather than
requesting or printing key material:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly publish switch -batch \
  noble s3:s3-gfx906:ubuntu <snapshot-name>
```

Confirm that the published repository now references the requested snapshot:

```bash
kubectl exec -n rocm-build aptly-0 -- aptly publish show noble \
  s3:s3-gfx906:ubuntu
```

Report the published snapshot name, target (`s3:s3-gfx906:ubuntu/noble`),
component (`main`), and the verified package count.
