# Song validator CI runner contract

The `CI` workflow uses a repository-scoped validation runner for trusted
same-repository pull requests and pushes to `main`. The runner must be online
with all of these labels:

```text
self-hosted, Linux, X64, pr-validation, stepmania-song-validator
```

Repository administrators provision and register the runner outside this
repository. Before changing or relying on the workflow selector, verify its
status and labels:

```bash
gh api repos/lancer1977/stepmania-song-validator/actions/runners \
  --jq '.runners[] | {name, status, busy, labels: [.labels[].name]}'
```

The expected repository-scoped runner name is
`arch-server-stepmania-song-validator-ci`. On `arch-server`, its files live at
`~/.local/share/github-runners/stepmania-song-validator-ci/` and its user
service is `github-runner@stepmania-song-validator-ci`. Follow an existing
validation runner's `config.sh` and systemd user-service pattern when replacing
the registration; registration tokens are short-lived and must never be saved
in this repository, documentation, logs, or shell history.

## Required capability and isolation

The runner needs Linux X64, Git, Bash, Python 3.11 support for
`actions/setup-python`, and outbound package access for `pip`. The workflow
keeps the existing `.[build]` installation, unit-test suite, package build, and
fixture-library CLI smoke checks in `scripts/validate.sh`.

This validation identity must not have PyPI publishing identity, GitHub release
write authority, deployment credentials, production secrets, SSH keys, a
Docker socket, physical-device access, or private-network capabilities
unrelated to package validation. Release and PyPI publication remain on their
separate workflow and authority boundary.

## Trust and capacity boundary

Same-repository pull requests and repository-owned `main` pushes may use the
persistent validation runner. A pull request whose head repository differs
from `github.repository` is skipped at the job boundary. There is deliberately
no GitHub-hosted fallback: record fork validation or unavailable trusted
capacity as a CI infrastructure blocker. To validate a fork contribution, a
maintainer must first review it without executing it, then reproduce the
accepted commit in a trusted repository branch and run CI there.

## Validation and exact-head proof

Run the same validation locally before opening a pull request:

```bash
python -m pip install ".[build]"
bash scripts/validate.sh
python -m unittest tests.test_ci_policy
git diff --check
```

The migration is proven only when an exact-head Actions job records the
complete runner label set, checks out the intended revision, and completes
`scripts/validate.sh`. A YAML change, queued job, skipped job, or job without
checkout and validation steps is not proof.
