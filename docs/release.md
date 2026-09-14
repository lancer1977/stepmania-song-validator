# Release operations

The `Release` workflow is a publication boundary. It is deliberately separate
from pull-request and `main`-push validation: routine changes never create a
GitHub release or publish to PyPI.

## Trigger

After the desired commit has landed on the protected `main` branch, a
repository administrator manually dispatches **Release** with the branch set
to `main` and the full 40-character SHA of the intended commit:

```bash
gh workflow run release.yml \
  --ref main \
  -f source_sha="$(git rev-parse origin/main)"
```

Both publication jobs require this exact `workflow_dispatch` event on
`refs/heads/main`. A dispatch from another ref is skipped. The workflow also
rejects abbreviated or non-lowercase SHAs and requires the selected commit to
be an ancestor of `origin/main`, so the trusted default-branch workflow cannot
publish an unrelated revision.

PyPI publication is independently gated by the
`PYPI_PUBLISHING_ENABLED=true` repository variable and PyPI Trusted Publishing
configuration. If either is absent, the PyPI job does not publish. GitHub
release creation remains a separate job and permission boundary.

## Rollback and retraction

This workflow creates a prerelease; it does not deploy software or mutate the
source branch. If a release is incorrect, an administrator should first mark
the GitHub prerelease as a draft or delete it, then retract or yank the PyPI
version according to PyPI policy. Published package versions are immutable, so
rollback means selecting a corrected commit and running a new explicit
dispatch; it does not rewrite tags or silently replace artifacts. No automatic
retraction is attempted by CI.
