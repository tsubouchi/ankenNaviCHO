import pytest
from pathlib import Path
from utils.common import acquire_app_lock


def test_acquire_app_lock_exclusive(tmp_path: Path):
    """同じロックファイルを二重取得すると BlockingIOError が発生することを確認"""
    lock_file = tmp_path / "anken_navi.lock"

    # 1回目は取得できる
    with acquire_app_lock(lock_file):
        # 2回目は例外
        with pytest.raises(BlockingIOError):
            with acquire_app_lock(lock_file):
                pass 