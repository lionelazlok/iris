import sqlite3

from conftest import ADMIN, AUDITOR, OPERATOR, enroll, png, verify


def test_enroll_and_verify_genuine(client):
    r = enroll(client, "EMP-001", 10)
    assert r.status_code == 200, r.text
    assert r.json()["algorithm"] == "AES-256-GCM"
    v = verify(client, "EMP-001", 10, 2)
    assert v.status_code == 200 and v.json()["match"] is True


def test_impostor_rejected(client):
    enroll(client, "EMP-002", 11)
    v = verify(client, "EMP-002", 12, 0)
    assert v.json()["match"] is False and v.json()["hamming_distance"] > 0.4


def test_duplicate_enrollment_refused(client):
    enroll(client, "EMP-003", 13)
    assert enroll(client, "EMP-003", 13, 1).status_code == 409


def test_no_api_key(client):
    r = client.post("/enroll", data={"external_ref": "X"}, files={"image": ("e.png", png(1, 0), "image/png")})
    assert r.status_code == 401


def test_rbac(client):
    assert client.get("/audit", headers=OPERATOR).status_code == 403
    assert client.post("/admin/rotate-keys", headers=OPERATOR).status_code == 403
    assert client.post("/admin/rotate-keys", headers=AUDITOR).status_code == 403
    assert enroll(client, "X", 1, headers=AUDITOR).status_code == 403
    assert client.get("/audit", headers=AUDITOR).status_code == 200


def test_invalid_image(client):
    r = client.post("/enroll", data={"external_ref": "BAD"},
                    files={"image": ("x.png", b"not an image", "image/png")}, headers=OPERATOR)
    assert r.status_code == 400


def test_db_contains_no_plain_template(client, settings):
    enroll(client, "EMP-004", 14)
    path = settings.database_url.removeprefix("sqlite:///")
    con = sqlite3.connect(path)
    blob = con.execute("select ciphertext from templates").fetchone()[0]
    assert not blob.startswith(b"IRT1")  # l'en-tête du format clair n'apparaît pas
    assert "image" not in [r[1] for r in con.execute("pragma table_info(templates)")]


def test_tampered_db_raises_integrity_alert(client, settings):
    enroll(client, "EMP-005", 15)
    path = settings.database_url.removeprefix("sqlite:///")
    con = sqlite3.connect(path)
    ct = bytearray(con.execute("select ciphertext from templates").fetchone()[0])
    ct[50] ^= 0xFF
    con.execute("update templates set ciphertext=?", (bytes(ct),)); con.commit()
    v = verify(client, "EMP-005", 15, 1)
    assert v.status_code == 409 and "INTÉGRITÉ" in v.json()["detail"]
    audit = client.get("/audit", headers=ADMIN).json()
    assert any(e["outcome"] == "integrity_alert" for e in audit)


def test_template_substitution_attack(client, settings):
    """L'attaquant copie le gabarit de Mallory sur la ligne d'Alice pour se faire passer pour elle."""
    enroll(client, "ALICE", 16)
    enroll(client, "MALLORY", 17)
    con = sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))
    m = con.execute("select t.ciphertext,t.nonce,t.wrapped_dek,t.dek_nonce from templates t join subjects s "
                    "on s.id=t.subject_id where s.external_ref='MALLORY'").fetchone()
    con.execute("update templates set ciphertext=?,nonce=?,wrapped_dek=?,dek_nonce=? where subject_id="
                "(select id from subjects where external_ref='ALICE')", m); con.commit()
    v = verify(client, "ALICE", 17, 1)  # Mallory présente son propre œil
    assert v.status_code == 409


def test_lockout_after_failures(client):
    enroll(client, "EMP-006", 18)
    for _ in range(5):
        assert verify(client, "EMP-006", 19, 0).json()["match"] is False
    assert verify(client, "EMP-006", 18, 1).status_code == 423


def test_rotation_keeps_verification_working(client):
    enroll(client, "EMP-007", 20)
    r = client.post("/admin/rotate-keys", headers=ADMIN).json()
    assert r["new_kek"] == "kek-v2" and r["templates_rewrapped"] == 1
    assert client.get("/subjects/EMP-007", headers=ADMIN).json()["templates"][0]["kek_id"] == "kek-v2"
    assert verify(client, "EMP-007", 20, 1).json()["match"] is True


def test_revoke_and_reenroll(client):
    enroll(client, "EMP-008", 21)
    assert client.post("/subjects/EMP-008/revoke", headers=ADMIN).status_code == 200
    assert verify(client, "EMP-008", 21, 1).status_code == 403
    r = client.post("/subjects/EMP-008/reenroll", files={"image": ("e.png", png(21, 2), "image/png")}, headers=ADMIN)
    assert r.json()["cancelable_version"] == 2
    assert verify(client, "EMP-008", 21, 1).json()["match"] is True


def test_delete_rgpd(client, settings):
    enroll(client, "EMP-009", 22)
    assert client.delete("/subjects/EMP-009", headers=ADMIN).status_code == 200
    assert client.get("/subjects/EMP-009", headers=ADMIN).status_code == 404
    con = sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))
    assert con.execute("select count(*) from templates").fetchone()[0] == 0


def test_audit_chain_detects_tampering(client, settings):
    enroll(client, "EMP-010", 23)
    verify(client, "EMP-010", 23, 1)
    assert client.get("/audit/verify", headers=AUDITOR).json()["valid"] is True
    con = sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))
    con.execute("update audit_logs set outcome='success' where action='verify'"); con.commit()
    res = client.get("/audit/verify", headers=AUDITOR).json()
    assert res["valid"] is False


def test_audit_chain_detects_deletion(client, settings):
    enroll(client, "EMP-011", 24)
    verify(client, "EMP-011", 24, 1)
    verify(client, "EMP-011", 24, 2)
    con = sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))
    con.execute("delete from audit_logs where id=2"); con.commit()
    assert client.get("/audit/verify", headers=AUDITOR).json()["valid"] is False


def test_unauthenticated_access_logged(client):
    client.get("/audit")
    log = client.get("/audit", headers=ADMIN).json()
    assert any(e["outcome"] == "unauthenticated" for e in log)
