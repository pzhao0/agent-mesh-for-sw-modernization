import os
import subprocess
import sys

import yaml
from conftest import REPO_ROOT, WORKFLOW_ROOT

EXPECTED_PIPELINES = {
    "analysis.yaml",
    "data_generation.yaml",
    "indexing.yaml",
    "multi_repo.yaml",
    "single_repo.yaml",
}


def test_all_pipelines_compile(tmp_path):
    env = os.environ | {
        "PYTHONPATH": str(WORKFLOW_ROOT),
        "PIPELINE_COMPILE_ONLY": "1",
        "KFP_PIPELINE_OUTPUT_DIR": str(tmp_path),
        "KFP_IMAGE_REGISTRY": "quay.io/test",
        "KFP_DATA_GENERATION_BASE_IMAGE_NAME": "data-generation",
        "KFP_DATA_GENERATION_BASE_IMAGE_TAG": "test",
        "KFP_INDEXING_BASE_IMAGE_NAME": "data-indexing",
        "KFP_INDEXING_BASE_IMAGE_TAG": "test",
        "KFP_ANALYSIS_BASE_IMAGE_NAME": "data-analysis",
        "KFP_ANALYSIS_BASE_IMAGE_TAG": "test",
        "AGENTMESH_REPO_URL": (
            "https://github.com/rh-ai-quickstart/" "agent-mesh-for-sw-modernization.git"
        ),
        "AGENTMESH_REPO_REF": "main",
        "GIT_USERNAME": "ci",
        "GIT_TOKEN": "unused",
    }

    subprocess.run(
        [sys.executable, str(WORKFLOW_ROOT / "pipelines" / "orchestrator.py")],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )

    generated = {path.name for path in tmp_path.glob("*.yaml")}
    assert generated == EXPECTED_PIPELINES

    for path in tmp_path.glob("*.yaml"):
        document = yaml.safe_load(path.read_text())
        assert document["pipelineInfo"]["name"]
        assert document["root"]["dag"]["tasks"]
