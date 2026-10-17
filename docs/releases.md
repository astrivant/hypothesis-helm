# Verified releases

<!-- toc:start -->
**Table of contents**

- [Configure signing](#configure-signing)
- [Publish and verify](#publish-and-verify)
- [Recover an interrupted publication](#recover-an-interrupted-publication)
<!-- toc:end -->

A tag release produces both a PyPI package and a GitHub release. Source verification,
publication and final download verification are separate gates in the same CI run.
The final gate rejects missing, draft, incomplete or mismatched releases, including
when a publisher was skipped. Manual benchmark refreshes are independent of releases.

## Configure signing

With GitHub CLI authentication and Cosign/OpenSSL installed, a maintainer explicitly
provisions one signing identity for this repository:

```bash
bash scripts/release/setup-signing.sh --repo astrivant/hypothesis-helm
```

The helper creates or reuses a complete key set under
`${XDG_DATA_HOME:-$HOME/.local/share}/hypothesis-helm/signing/astrivant-hypothesis-helm`.
Use `--key-dir` for an existing protected backup. Partial key sets fail without
replacement. It uploads `COSIGN_PRIVATE_KEY`, `COSIGN_PASSWORD` and the public
`COSIGN_PUBLIC_KEY_SHA256` variable. Retain that fingerprint independently of
release attachments. No key material belongs in Git or build artifacts.

The PyPI job runs in the `pypi` environment and uses the existing `PYPI_API_TOKEN` secret.
Only the tag publisher receives signing secrets and repository write permission.
PR tests create disposable synthetic keys; they never receive release credentials.

## Publish and verify

Push a new signed version tag after reviewing and merging the tested source. The
build stamps the tag version before producing the wheel and source archive. Both
publishers consume that run's exact artifacts, without rebuilding them.

The GitHub publisher downloads the PyPI files and checks their SHA-256 hashes
against the build. It signs the distributions and a complete checksum manifest,
uploads to a draft, downloads and verifies every attachment, then publishes.
Attachments include the two distributions, their signature bundles, `SHA256SUMS`
and its bundle, `cosign.pub`, `public-key.sha256` and `SOURCE.json` binding the tag
and source commit. The signature mode uses repository keys without a transparency
log; verification requires the independently trusted key fingerprint.

From a checkout containing these tools, with Python, packaging, gh, Cosign and
OpenSSL installed:

```bash
export GITHUB_REPOSITORY=astrivant/hypothesis-helm
export RELEASE_TAG=vX.Y.Z
export SOURCE_SHA=FULL_TAGGED_COMMIT
export COSIGN_PUBLIC_KEY_SHA256=INDEPENDENTLY_TRUSTED_FINGERPRINT
bash scripts/release/verify-published.sh
```

The verifier downloads both GitHub and PyPI outputs, checks complete attachment
membership, source bindings and signatures, and fails on yanked or altered registry
files. A public release is immutable; retrying publication only verifies it.

## Recover an interrupted publication

Use the original successful run's `python-distributions-VERSION` artifact. Confirm
its tag, source commit and successful verification jobs before recovery. Do not move
the tag, rebuild different package bytes or replace an existing public release.
Set the variables above plus `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD` from the
protected signing configuration, without placing their values in command arguments.

```bash
export DISTRIBUTION_DIRECTORY=/protected/original-build/dist
bash scripts/release/publish.sh
bash scripts/release/verify-published.sh
```

Recovery can run these reviewed tools from a newer checkout while retaining the
original `SOURCE_SHA`. The tag must still resolve to that commit on `origin/main`.
Draft retries compare existing payloads before replacing incomplete uploads. PyPI
retries skip existing filenames, but GitHub publication then verifies all registry
bytes against the original build. Conflicting content fails rather than being replaced.
