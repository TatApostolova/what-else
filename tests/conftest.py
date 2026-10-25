import dataclasses

import pytest

from whatelse.config import load_settings


@pytest.fixture
def settings(tmp_path):
    """Real config, but data (DB, logs) in a temporary folder."""
    return dataclasses.replace(load_settings("real"), data_dir=tmp_path)
