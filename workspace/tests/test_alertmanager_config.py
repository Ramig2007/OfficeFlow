import pytest

from scripts.render_alertmanager_config import render_config


def test_default_alertmanager_config_disables_delivery_explicitly():
    config = render_config("", "")
    assert "receiver: null-receiver" in config
    assert "null-receiver" in config
    assert "webhook_configs" not in config
    assert "telegram_configs" not in config


def test_https_webhook_is_rendered_as_alertmanager_receiver():
    config = render_config("https://hooks.example.test/officeflow", "")
    assert "receiver: officeflow-notifications" in config
    assert 'url: "https://hooks.example.test/officeflow"' in config
    assert "send_resolved: true" in config


def test_webhook_bearer_token_is_rendered_without_interpolation():
    config = render_config("https://hooks.example.test/officeflow", "ci-only-token")
    assert "type: Bearer" in config
    assert 'credentials: "ci-only-token"' in config


def test_telegram_receiver_is_rendered_with_integer_chat_id():
    config = render_config("", "", "123456:ci-only-token", "-1001234567890")
    assert "receiver: officeflow-notifications" in config
    assert 'bot_token: "123456:ci-only-token"' in config
    assert "chat_id: -1001234567890" in config
    assert "telegram_configs:" in config
    assert "send_resolved: true" in config


def test_telegram_and_webhook_can_share_one_receiver():
    config = render_config(
        "https://hooks.example.test/officeflow",
        "",
        "123456:ci-only-token",
        "123456789",
    )
    assert "telegram_configs:" in config
    assert "webhook_configs:" in config


def test_telegram_credentials_must_be_supplied_together():
    with pytest.raises(ValueError, match="must be set together"):
        render_config("", "", "123456:ci-only-token", "")


def test_telegram_chat_id_must_be_integer():
    with pytest.raises(ValueError, match="must be an integer"):
        render_config("", "", "123456:ci-only-token", "not-a-chat-id")


def test_telegram_chat_id_must_not_be_zero():
    with pytest.raises(ValueError, match="must not be zero"):
        render_config("", "", "123456:ci-only-token", "0")


def test_telegram_token_rejects_control_characters():
    with pytest.raises(ValueError, match="must not contain whitespace"):
        render_config("", "", "123456:token\\nforged", "123456789")


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.test/officeflow",
        "https://user:password@hooks.example.test/officeflow",
        "https://hooks.example.test/officeflow#fragment",
        "https://hooks.example.test:invalid/officeflow",
        "https://hooks.example.test/officeflow\\nroute: injected",
    ],
)
def test_webhook_rejects_insecure_or_malformed_urls(url):
    with pytest.raises(ValueError):
        render_config(url, "")


def test_bearer_token_requires_a_webhook_url():
    with pytest.raises(ValueError, match="requires ALERTMANAGER_WEBHOOK_URL"):
        render_config("", "ci-only-token")


def test_bearer_token_rejects_line_breaks():
    with pytest.raises(ValueError, match="must not contain line breaks"):
        render_config("https://hooks.example.test/officeflow", "token\\nforged")
