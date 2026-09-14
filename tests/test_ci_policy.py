from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRUSTED_RUNNER = (
    "runs-on: [self-hosted, Linux, X64, pr-validation, stepmania-song-validator]"
)
FORK_GUARD = (
    "if: github.event_name != 'pull_request' || "
    "github.event.pull_request.head.repo.full_name == github.repository"
)
FORK_BLOCKER = "if: github.event.pull_request.head.repo.full_name != github.repository"


class WorkflowRunnerPolicyTests(unittest.TestCase):
    def read_workflow(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text()

    def test_ci_preserves_validation_contract_on_trusted_runner(self):
        workflow = self.read_workflow("ci.yml")

        self.assertIn("  test:\n", workflow)
        self.assertIn(TRUSTED_RUNNER, workflow)
        self.assertIn(FORK_GUARD, workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("uses: actions/setup-python@v5", workflow)
        self.assertIn('python-version: "3.11"', workflow)
        self.assertNotIn("/usr/bin/python3.11", workflow)
        self.assertIn('run: python -m pip install ".[build]"', workflow)
        self.assertIn("run: bash scripts/validate.sh", workflow)
        self.assertNotIn("ubuntu-latest", workflow)

    def test_fork_prs_fail_without_executing_fork_code(self):
        workflow = self.read_workflow("untrusted-pr-blocker.yml")

        self.assertIn("pull_request_target:", workflow)
        self.assertIn(FORK_BLOCKER, workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertNotIn(TRUSTED_RUNNER, workflow)
        self.assertIn("exit 1", workflow)
        self.assertIn("reproduce the accepted commit", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("github.event.pull_request.head.sha", workflow)
        self.assertNotIn("github.event.pull_request.head.ref", workflow)

    def test_release_workflow_stays_outside_validation_runner(self):
        workflow = self.read_workflow("release.yml")

        self.assertNotIn("stepmania-song-validator]", workflow)

    def test_release_write_authority_is_default_branch_dispatch_only(self):
        workflow = self.read_workflow("release.yml")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:\n", workflow)
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'",
            workflow,
        )
        self.assertIn("contents: write", workflow)
        self.assertIn("git merge-base --is-ancestor \"$SOURCE_SHA\" refs/remotes/origin/main", workflow)
        self.assertIn("[[ \"$SOURCE_SHA\" =~ ^[0-9a-f]{40}$ ]]", workflow)
        self.assertEqual(workflow.count("    if:"), 2)

    def test_release_contract_is_documented(self):
        docs = (ROOT / "docs" / "release.md").read_text()

        self.assertIn("workflow_dispatch", docs)
        self.assertIn("refs/heads/main", docs)
        self.assertIn("rollback", docs.lower())
        self.assertIn("PyPI", docs)


if __name__ == "__main__":
    unittest.main()
