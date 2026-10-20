import smtplib

from enferno import commands
from enferno.extensions import mail


def test_mail_test_sends_one_message(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_SERVER", "smtp.example.com")
    monkeypatch.setitem(app.config, "SECURITY_EMAIL_SENDER", "noreply@example.com")

    with mail.record_messages() as outbox:
        result = app.test_cli_runner().invoke(
            commands.mail_test, ["--to", "you@example.com"]
        )

    assert result.exit_code == 0, result.output
    assert len(outbox) == 1
    assert outbox[0].recipients == ["you@example.com"]
    assert outbox[0].sender == "noreply@example.com"
    assert "you@example.com" in result.output


def test_mail_test_requires_mail_server(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_SERVER", None)

    with mail.record_messages() as outbox:
        result = app.test_cli_runner().invoke(
            commands.mail_test, ["--to", "you@example.com"]
        )

    assert result.exit_code == 1
    assert "MAIL_SERVER" in result.output
    assert outbox == []


def test_mail_test_reports_smtp_errors_without_password(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_SERVER", "smtp.example.com")
    monkeypatch.setitem(app.config, "MAIL_PASSWORD", "private-mail-password")

    def fail(message):
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(mail, "send", fail)
    result = app.test_cli_runner().invoke(
        commands.mail_test, ["--to", "you@example.com"]
    )

    assert result.exit_code == 1
    assert "SMTPAuthenticationError" in result.output
    assert "private-mail-password" not in result.output
