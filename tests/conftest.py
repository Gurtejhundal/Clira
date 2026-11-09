import shutil
import subprocess

import pytest

from clira.config import Config
from clira.service import DEMO_CHANNEL, Service


@pytest.fixture
def service(tmp_path):
    return Service(Config(data_dir=tmp_path / "state", mode="demo", model="offline", enable_writes=False))


@pytest.fixture(scope="session")
def sample_mp4(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required for real MP4 validation test")
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=160x90:d=1",
            "-c:v",
            "mpeg4",
            "-y",
            str(path),
        ],
        check=True,
        timeout=30,
    )
    return path


@pytest.fixture
def prepared(service, sample_mp4):
    path = service.config.import_dir / "sample.mp4"
    shutil.copyfile(sample_mp4, path)
    asset = service.tool(
        DEMO_CHANNEL,
        "import_video",
        {
            "path": str(path),
            "rights": "original",
            "rights_evidence": "Created by test fixture; silent original color sample.",
            "creative_reviewed": True,
        },
    )
    assert asset["ok"], asset
    metadata = service.tool(
        DEMO_CHANNEL,
        "package_video",
        {
            "title": "A reviewed test video",
            "description": "Only a test",
            "tags": ["test"],
            "made_for_kids": False,
            "synthetic_media": False,
        },
    )
    assert metadata["ok"], metadata
    request = service.tool(
        DEMO_CHANNEL,
        "prepare_upload",
        {"asset_id": asset["data"]["id"], "metadata_id": metadata["data"]["id"]},
    )
    assert request["ok"], request
    return {"asset": asset["data"], "metadata": metadata["data"], **request["data"]}
