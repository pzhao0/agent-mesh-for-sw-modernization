import sys
from types import ModuleType

from pipelines.base import data_generation


def disable_telemetry(monkeypatch):
    telemetry_module = ModuleType("telemetry.default_custom_telemetry")

    class NoopTelemetry:
        def track(self):
            return None

    telemetry_module.DefaultCustomTelemetry = NoopTelemetry
    monkeypatch.setitem(
        sys.modules,
        "telemetry.default_custom_telemetry",
        telemetry_module,
    )


def test_data_generation_runs_code_and_config_passes(monkeypatch):
    disable_telemetry(monkeypatch)
    calls = []

    monkeypatch.setattr(
        data_generation,
        "generate_git_slug",
        lambda repo, branch: "example-repo-main",
    )
    monkeypatch.setattr(data_generation, "prepare_environment", lambda **kwargs: None)
    monkeypatch.setattr(data_generation, "detect_languages", lambda path: ["python"])
    monkeypatch.setattr(data_generation, "load_external_data", lambda path: {})
    monkeypatch.setattr(
        data_generation,
        "generate_code_and_meta",
        lambda **kwargs: calls.append(kwargs),
    )

    result = data_generation.DataGenerationPipeline().run(
        git_repo="https://github.com/example/repo",
        git_branch="main",
        source_path="source",
        target_path="target",
    )

    assert result == {
        "git_slug": "example-repo-main",
        "status": "complete",
        "fail_message": "",
    }
    assert [call["config"] for call in calls] == [False, True]


def test_data_generation_cleans_up_after_failure(monkeypatch):
    disable_telemetry(monkeypatch)
    cleanups = []

    monkeypatch.setattr(
        data_generation,
        "generate_git_slug",
        lambda repo, branch: "example-repo-main",
    )

    def fail_to_prepare(**kwargs):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(data_generation, "prepare_environment", fail_to_prepare)
    monkeypatch.setattr(
        data_generation,
        "reset_environment",
        lambda source, target: cleanups.append((source, target)),
    )

    result = data_generation.DataGenerationPipeline().run(
        git_repo="https://github.com/example/repo",
        git_branch="main",
        source_path="source",
        target_path="target",
    )

    assert result["git_slug"] == "example-repo-main"
    assert result["status"] == "error"
    assert "clone failed" in result["fail_message"]
    assert cleanups == [("source", "target")]
