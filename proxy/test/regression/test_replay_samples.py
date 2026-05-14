from pathlib import Path

from proxy.observability.replay_runner import replay_sample_file


def test_approved_samples_replay_cleanly():
    approved_dir = Path("proxy/test/samples/approved")
    assert approved_dir.exists()
    sample_files = sorted(approved_dir.glob("*.json"))
    assert sample_files
    for sample_file in sample_files:
        result = replay_sample_file(sample_file)
        assert result.ok, sample_file.as_posix()

