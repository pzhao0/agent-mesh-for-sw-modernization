import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPO_ROOT / "workflows" / "examples" / "code_understanding"

sys.path.insert(0, str(WORKFLOW_ROOT))
