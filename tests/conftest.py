import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from tools.synth_iris import capture  # noqa: E402

ADMIN = {"X-API-Key": "admin-demo-key"}
OPERATOR = {"X-API-Key": "operator-demo-key"}
AUDITOR = {"X-API-Key": "auditor-demo-key"}


def png(subject: int, session: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(capture(subject, session)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.database_url = f"sqlite:///{tmp_path}/test.db"
    s.keystore_path = tmp_path / "keystore.json"
    s.master_key_b64 = None
    return s


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def enroll(client, ref, subject, session=0, headers=OPERATOR):
    return client.post("/enroll", data={"external_ref": ref},
                       files={"image": ("eye.png", png(subject, session), "image/png")}, headers=headers)


def verify(client, ref, subject, session=1, headers=OPERATOR):
    return client.post("/verify", data={"external_ref": ref},
                       files={"image": ("eye.png", png(subject, session), "image/png")}, headers=headers)
