"""Exercise bump PR creation and updates with real local Git remotes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/create-version-bump-pr.yml").read_text())
CREATE_PR = next(
    step["run"] for step in WORKFLOW["jobs"]["create-pr"]["steps"] if step.get("id") == "pr"
)
PR_URL = "https://github.com/example/project/pull/1"


def git(repo, *args):
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.mark.parametrize("version", ["v0.1.7", "v0.2.0"])
def test_creates_then_refreshes_version_pr_from_current_main(tmp_path, version):
    branch = f"chore/bump-base-version-to-{version}"
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Workflow Test")
    git(repo, "config", "user.email", "workflow-test@example.com")
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "Makefile").write_text("BASE_VERSION ?= v0.1.6\n")
    git(repo, "add", "Makefile")
    git(repo, "commit", "-m", "initial main")
    git(repo, "push", "origin", "main")

    # Stub only the external PR API; branch creation, commits, and pushes are real.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state_file = tmp_path / "prs.json"
    gh = bin_dir / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "state_file = Path(os.environ['PR_STATE'])\n"
        "state = json.loads(state_file.read_text()) if state_file.exists() else []\n"
        "args = sys.argv[1:]\n"
        "assert os.environ['GH_TOKEN'] == 'test-token'\n"
        "assert os.environ['GH_REPO'] == 'example/project'\n"
        "branch = 'chore/bump-base-version-to-' + os.environ['NEW_VERSION']\n"
        "if args[:2] == ['pr', 'list']:\n"
        "    assert args[args.index('--base') + 1] == 'main'\n"
        "    assert args[args.index('--head') + 1] == branch\n"
        "    print('1' if state else '')\n"
        "elif args[:2] in (['pr', 'create'], ['pr', 'edit']):\n"
        "    creating = args[1] == 'create'\n"
        "    assert creating == (not state)\n"
        "    if creating:\n"
        "        assert args[args.index('--base') + 1] == 'main'\n"
        "        assert args[args.index('--head') + 1] == branch\n"
        "    else:\n"
        "        assert args[2] == '1'\n"
        "    state.append({'operation': args[1], 'title': args[args.index('--title') + 1],\n"
        "                  'body': Path(args[args.index('--body-file') + 1]).read_text()})\n"
        "    state_file.write_text(json.dumps(state))\n"
        f"    print({PR_URL!r})\n"
        "elif args[:2] == ['pr', 'view']:\n"
        "    assert args[2] == '1'\n"
        f"    print({PR_URL!r})\n"
        "else:\n"
        "    raise AssertionError(args)\n"
    )
    gh.chmod(0o755)

    for attempt in range(2):
        git(repo, "checkout", "main")
        if attempt:
            # Simulate a fresh Actions checkout after main has advanced.
            git(repo, "branch", "-D", branch)
            (repo / "new-source.txt").write_text("new main content\n")
            git(repo, "add", "new-source.txt")
            git(repo, "commit", "-m", "advance main")
            git(repo, "push", "origin", "main")
        main_sha = git(repo, "rev-parse", "HEAD")
        (repo / "Makefile").write_text(f"BASE_VERSION ?= {version}\n")
        (repo / "unrelated.txt").write_text("must not be committed\n")
        output = tmp_path / f"output-{attempt}"
        result = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", CREATE_PR],
            cwd=repo,
            env={
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "GH_TOKEN": "test-token",
                "GH_REPO": "example/project",
                "PR_STATE": str(state_file),
                "PREVIOUS_VERSION": "v0.1.6",
                "NEW_VERSION": version,
                "RUNNER_TEMP": str(tmp_path),
                "GITHUB_OUTPUT": str(output),
                "GITHUB_ACTOR": "maintainer",
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_REPOSITORY": "example/project",
                "GITHUB_RUN_ID": "42",
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert output.read_text() == f"pull-request-url={PR_URL}\n"
        assert git(repo, "rev-parse", "HEAD^") == main_sha
        assert git(remote, "rev-parse", branch) == git(repo, "rev-parse", "HEAD")
        assert git(repo, "diff", "--name-only", "main", "HEAD") == "Makefile"
        assert git(repo, "show", "HEAD:Makefile") == f"BASE_VERSION ?= {version}"

    state = json.loads(state_file.read_text())
    assert [entry["operation"] for entry in state] == ["create", "edit"]
    assert state[-1]["title"] == f"chore: bump BASE_VERSION to {version}"
    assert f"v0.1.6 to {version}" in state[-1]["body"]
    assert "https://github.com/example/project/actions/runs/42" in state[-1]["body"]
