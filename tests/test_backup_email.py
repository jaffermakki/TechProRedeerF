"""
Tests for emailing a full data backup — both the on-demand "Send Test
Backup" button and the automatic weekly job. Network calls are mocked
throughout, same convention as test_email_brevo.py: this confirms the
app builds and dispatches the right thing, not that Brevo/SMTP servers
are reachable.
"""
import json
from unittest.mock import patch, MagicMock

from app.notifications import send_backup_email
from app.main import set_setting, get_setting, build_backup_json, backup_filename, run_weekly_backup_email_job


def _set(db_session, key, value):
    set_setting(db_session, key, value)


# ── build_backup_json() — the shared content both paths send ───────────

def test_build_backup_json_has_the_expected_shape(db_session):
    raw = build_backup_json(db_session)
    data = json.loads(raw)
    assert data["version"] == 1
    for key in ("settings", "products", "customers", "repairs", "invoices", "staff"):
        assert key in data


def test_build_backup_json_excludes_pin_hashes(db_session):
    raw = build_backup_json(db_session)
    data = json.loads(raw)
    assert len(data["staff"]) > 0
    for s in data["staff"]:
        assert "pin_hash" not in s


def test_backup_filename_is_dated():
    from datetime import datetime
    name = backup_filename()
    assert name.startswith("techpro_backup_")
    assert datetime.utcnow().strftime("%Y-%m-%d") in name


# ── send_backup_email() — dispatch + attachment building ───────────────

def test_backup_email_dispatches_to_brevo_with_the_attachment(db_session):
    _set(db_session, "email_method", "brevo_api")
    from app.encryption import encrypt_value
    _set(db_session, "brevo_api_key", encrypt_value("fake-key"))
    _set(db_session, "brevo_from_email", "shop@example.com")

    with patch("app.notifications._send_via_brevo_api") as mock_brevo:
        mock_brevo.return_value = (True, "Accepted by Brevo's API.")
        ok, msg = send_backup_email(db_session, "owner@example.com", b'{"fake":"backup"}',
                                     "test_backup.json", get_setting)
    assert ok
    _, kwargs = mock_brevo.call_args
    assert kwargs["attachment_name"] == "test_backup.json"
    assert kwargs["attachment_content"] == b'{"fake":"backup"}'


def test_backup_email_dispatches_to_smtp_with_a_real_mime_attachment(db_session):
    _set(db_session, "email_method", "smtp")
    _set(db_session, "smtp_host", "smtp.example.com")
    _set(db_session, "smtp_port", "587")
    _set(db_session, "smtp_user", "shop@example.com")
    from app.encryption import encrypt_value
    _set(db_session, "smtp_password", encrypt_value("fakepass"))
    _set(db_session, "smtp_from", "shop@example.com")

    captured = {}
    def fake_send(host, port, user, password, msg):
        captured["msg"] = msg
        return True, "sent"

    with patch("app.notifications._send_via_smtp", side_effect=fake_send):
        ok, msg = send_backup_email(db_session, "owner@example.com", b'{"fake":"backup"}',
                                     "test_backup.json", get_setting)
    assert ok
    # Decode the actual MIME message and confirm the attachment survives
    # real email encoding, not just that a function was called correctly.
    raw = captured["msg"].as_string()
    import email as email_lib
    parsed = email_lib.message_from_string(raw)
    found_attachment = False
    for part in parsed.walk():
        if part.get_filename() == "test_backup.json":
            found_attachment = True
            payload = part.get_payload(decode=True)
            assert payload == b'{"fake":"backup"}'
    assert found_attachment, "backup attachment did not survive MIME encoding"


def test_backup_email_fails_clearly_when_brevo_not_configured(db_session):
    _set(db_session, "email_method", "brevo_api")
    _set(db_session, "brevo_api_key", "")
    _set(db_session, "brevo_from_email", "")
    ok, msg = send_backup_email(db_session, "owner@example.com", b"{}", "b.json", get_setting)
    assert not ok
    assert "Brevo" in msg


def test_backup_email_fails_clearly_when_smtp_not_configured(db_session):
    _set(db_session, "email_method", "smtp")
    _set(db_session, "smtp_host", "")
    ok, msg = send_backup_email(db_session, "owner@example.com", b"{}", "b.json", get_setting)
    assert not ok
    assert "not configured" in msg.lower()


# ── /settings/send-test-backup route ────────────────────────────────────

def test_send_test_backup_requires_owner_role(manager_client):
    resp = manager_client.post("/settings/send-test-backup")
    assert resp.status_code == 403


def test_send_test_backup_fails_gracefully_with_no_recipient(owner_client, db_session):
    _set(db_session, "backup_email", "")
    _set(db_session, "digest_email", "")
    resp = owner_client.post("/settings/send-test-backup", follow_redirects=False)
    assert resp.status_code == 303
    page = owner_client.get("/settings")
    assert "backup email address" in page.text.lower()


def test_send_test_backup_uses_backup_email_over_digest_email(owner_client, db_session):
    """backup_email should win when both are set — digest_email is only
    the fallback for shops that don't bother setting a separate one."""
    _set(db_session, "backup_email", "backup-specific@example.com")
    _set(db_session, "digest_email", "digest-only@example.com")
    _set(db_session, "email_method", "brevo_api")
    from app.encryption import encrypt_value
    _set(db_session, "brevo_api_key", encrypt_value("fake-key"))
    _set(db_session, "brevo_from_email", "shop@example.com")

    with patch("app.notifications._send_via_brevo_api") as mock_brevo:
        mock_brevo.return_value = (True, "Accepted by Brevo's API.")
        resp = owner_client.post("/settings/send-test-backup", follow_redirects=False)
    assert resp.status_code == 303
    args, kwargs = mock_brevo.call_args
    assert "backup-specific@example.com" in args


def test_send_test_backup_falls_back_to_digest_email(owner_client, db_session):
    _set(db_session, "backup_email", "")
    _set(db_session, "digest_email", "digest-only@example.com")
    _set(db_session, "email_method", "brevo_api")
    from app.encryption import encrypt_value
    _set(db_session, "brevo_api_key", encrypt_value("fake-key"))
    _set(db_session, "brevo_from_email", "shop@example.com")

    with patch("app.notifications._send_via_brevo_api") as mock_brevo:
        mock_brevo.return_value = (True, "Accepted by Brevo's API.")
        owner_client.post("/settings/send-test-backup", follow_redirects=False)
    args, kwargs = mock_brevo.call_args
    assert "digest-only@example.com" in args


# ── Settings persistence ────────────────────────────────────────────────

def test_settings_save_persists_backup_email_fields(owner_client, db_session):
    resp = owner_client.post("/settings", data={
        "shop_name": "TechPro+", "province": "ON", "invoice_prefix": "INV",
        "points_per_dollar": "1", "points_redeem_rate": "100", "digest_hour": "21",
        "backup_email_enabled": "on", "backup_email": "weekly-backup@example.com",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert get_setting(db_session, "backup_email_enabled", "") == "true"
    assert get_setting(db_session, "backup_email", "") == "weekly-backup@example.com"


def test_settings_save_disables_backup_email_when_checkbox_unchecked(owner_client, db_session):
    _set(db_session, "backup_email_enabled", "true")
    resp = owner_client.post("/settings", data={
        "shop_name": "TechPro+", "province": "ON", "invoice_prefix": "INV",
        "points_per_dollar": "1", "points_redeem_rate": "100", "digest_hour": "21",
        # backup_email_enabled deliberately omitted -- an unchecked checkbox
        # sends nothing at all, same as every other checkbox in this form.
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert get_setting(db_session, "backup_email_enabled", "") == "false"


# ── The scheduled job's own conditional logic ───────────────────────────

def test_weekly_backup_job_does_nothing_when_disabled(db_session):
    _set(db_session, "backup_email_enabled", "false")
    with patch("app.main.send_backup_email") as mock_send:
        run_weekly_backup_email_job()
    mock_send.assert_not_called()


def test_weekly_backup_job_does_nothing_with_no_recipient(db_session):
    _set(db_session, "backup_email_enabled", "true")
    _set(db_session, "backup_email", "")
    _set(db_session, "digest_email", "")
    with patch("app.main.send_backup_email") as mock_send:
        run_weekly_backup_email_job()
    mock_send.assert_not_called()


def test_weekly_backup_job_sends_and_records_last_backup_when_configured(db_session):
    _set(db_session, "backup_email_enabled", "true")
    _set(db_session, "backup_email", "owner@example.com")
    with patch("app.main.send_backup_email") as mock_send:
        mock_send.return_value = (True, "Backup emailed.")
        run_weekly_backup_email_job()
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert "owner@example.com" in args
    assert get_setting(db_session, "last_backup", "") != ""
