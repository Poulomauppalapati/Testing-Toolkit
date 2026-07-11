from pathlib import Path

from agent.jobs import JobManager


def test_resumable_job_recovers_after_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "registry.json"
    first = JobManager(state_path)
    job = first.create(
        "kb_index",
        project="Demo",
        resumable=True,
        recovery={"project": "Demo", "force": False},
    )
    job.set_progress("Embedding", 4, 10)
    job.checkpoint(document="guide.pdf", chunk=42)

    second = JobManager(state_path)
    recovered = second.get(job.id)

    assert recovered is not None
    assert recovered.state == "recovering"
    assert recovered.interrupted is True
    assert recovered.progress_stage == "Embedding"
    assert recovered.progress_current == 4
    assert recovered.recovery["document"] == "guide.pdf"
    assert second.find_active("kb_index", "Demo") is recovered


def test_non_resumable_job_fails_closed_after_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "registry.json"
    first = JobManager(state_path)
    job = first.create("push", project="Demo", resumable=False)

    second = JobManager(state_path)
    recovered = second.get(job.id)

    assert recovered is not None
    assert recovered.state == "error"
    assert "restart" in recovered.error.lower()
    assert second.find_active("push", "Demo") is None


def test_terminal_job_survives_for_reattachment(tmp_path: Path) -> None:
    state_path = tmp_path / "registry.json"
    first = JobManager(state_path)
    job = first.create("kb_context", project="Demo", resumable=True)
    job.finish({"status": "complete"})

    second = JobManager(state_path)
    recovered = second.get(job.id)

    assert recovered is not None
    assert recovered.state == "done"
    assert recovered.result == {"status": "complete"}
