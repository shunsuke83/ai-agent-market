from pathlib import Path

from g2b.sync_d1 import sync_notices_to_d1

ROOT = Path(__file__).resolve().parents[2]


def test_sync_d1_dry_run_builds_rows():
    summary = sync_notices_to_d1(ROOT, dry_run=True, limit=3)
    assert summary["dry_run"] is True
    assert summary["notices"] >= 1
    assert summary["sample"] is not None
