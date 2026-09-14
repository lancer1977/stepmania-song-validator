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
        self.assertIn(TRUSTED_RUNNER, workflow)
        self.assertIn("exit 1", workflow)
        self.assertIn("reproduce the accepted commit", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("github.event.pull_request.head.sha", workflow)
        self.assertNotIn("github.event.pull_request.head.ref", workflow)

    def test_release_workflow_stays_outside_validation_runner(self):
        workflow = self.read_workflow("release.yml")

        self.assertNotIn("stepmania-song-validator]", workflow)


if __name__ == "__main__":
    unittest.main()
