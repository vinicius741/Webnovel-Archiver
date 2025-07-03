import os
import pytest
import tempfile
import shutil


@pytest.fixture(autouse=True)
def isolated_workspace(monkeypatch):
    """Isolate the workspace for each test."""
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("WNA_WORKSPACE_ROOT", temp_dir)
        yield temp_dir
