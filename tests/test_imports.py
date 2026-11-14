import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_package_import_does_not_require_configured_settings():
    project_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.pop("DJANGO_SETTINGS_MODULE", None)
    env["PYTHONPATH"] = str(project_root / "src")

    result = subprocess.run(
        [sys.executable, "-c", "import django_boosted"],
        cwd=project_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_drf_metadata_merges_extra_metadata():
    serializers = pytest.importorskip("rest_framework.serializers")
    from django_boosted.rest_framework.metadata import BoostedRestFrameworkMetadata

    field = serializers.CharField()
    field.extra_metadata = {"widget": "secret"}

    info = BoostedRestFrameworkMetadata().get_field_info(field)

    assert info["widget"] == "secret"
