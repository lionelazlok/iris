import os

import numpy as np
import pytest

from app.crypto_service import CryptoService, EncryptedBlob, IntegrityError, KeyStore
from app.iris_engine import IrisEngine, hamming_distance
from app.template_codec import cancelable_transform, deserialize, serialize
from tools.synth_iris import capture


@pytest.fixture
def ks(tmp_path):
    return KeyStore(tmp_path / "ks.json", os.urandom(32))


def tpl():
    return IrisEngine().extract(capture(5, 0))


def test_serialize_roundtrip():
    t = tpl()
    t2 = deserialize(serialize(t))
    assert (t.code == t2.code).all() and (t.mask == t2.mask).all()


def test_encrypt_decrypt_roundtrip(ks):
    c = CryptoService(ks)
    data = serialize(tpl())
    blob = c.encrypt(data, "subj", "tpl")
    assert data not in blob.ciphertext and len(blob.nonce) == 12
    assert c.decrypt(blob, "subj", "tpl") == data


def test_nonces_and_ciphertexts_unique(ks):
    c = CryptoService(ks)
    data = serialize(tpl())
    b1, b2 = c.encrypt(data, "s", "t"), c.encrypt(data, "s", "t")
    assert b1.nonce != b2.nonce and b1.ciphertext != b2.ciphertext


def test_bitflip_detected(ks):
    c = CryptoService(ks)
    b = c.encrypt(serialize(tpl()), "s", "t")
    ct = bytearray(b.ciphertext); ct[100] ^= 0x01
    with pytest.raises(IntegrityError):
        c.decrypt(EncryptedBlob(bytes(ct), b.nonce, b.wrapped_dek, b.dek_nonce, b.kek_id), "s", "t")


def test_swap_to_other_subject_detected(ks):
    c = CryptoService(ks)
    b = c.encrypt(serialize(tpl()), "alice", "t1")
    with pytest.raises(IntegrityError):
        c.decrypt(b, "mallory", "t1")  # AAD différente


def test_wrong_master_key_rejected(tmp_path):
    KeyStore(tmp_path / "ks.json", os.urandom(32))
    with pytest.raises(IntegrityError):
        KeyStore(tmp_path / "ks.json", os.urandom(32))


def test_keystore_file_has_no_plain_keys(ks):
    raw = ks.path.read_text()
    assert "kek-v1" not in raw and "cancel_secret" not in raw


def test_rotation_rewrap(ks):
    c = CryptoService(ks)
    data = serialize(tpl())
    b = c.encrypt(data, "s", "t")
    ks.rotate()
    b2 = c.rewrap(b, "s", "t")
    assert b2.kek_id == "kek-v2" and c.decrypt(b2, "s", "t") == data


def test_cancelable_preserves_distance_and_hides_code():
    e = IrisEngine()
    a, b = e.extract(capture(6, 0)), e.extract(capture(6, 1))
    sec = os.urandom(32)
    ta, tb = cancelable_transform(a, sec, "s", 1), cancelable_transform(b, sec, "s", 1)
    assert hamming_distance(a.code, a.mask, b.code, b.mask) == pytest.approx(
        hamming_distance(ta.code, ta.mask, tb.code, tb.mask))
    assert np.mean(ta.code == a.code) < 0.6  # code transformé ≠ code brut


def test_revoked_version_unlinkable():
    a = IrisEngine().extract(capture(7, 0))
    sec = os.urandom(32)
    v1, v2 = cancelable_transform(a, sec, "s", 1), cancelable_transform(a, sec, "s", 2)
    # Même œil, versions différentes : comparables à deux iris quelconques (≈ 0,5)
    assert hamming_distance(v1.code, v1.mask, v2.code, v2.mask) > 0.45
