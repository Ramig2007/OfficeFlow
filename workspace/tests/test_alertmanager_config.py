import pytest

from scripts.render_alertmanager_config import render_config


def test_default_alertmanager_config_disables_delivery_explicitly():
    config = render_config("", "")
    assert "receiver: null-receiver" in config
    assert "null-receiver" in config
    assert "webhook_configs" not in config


def test_https_webhook_is_rendered_as_alertmanager_receiver():
    config = render_config("https://hooks.example.test/officeflow", "")
    assert "receiver: officeflow-webhook" in config
    assert 'url: "https://hooks.example.test/officeflow"' in config
    assert "send_resolved: true" in config


def test_webhook_bearer_token_is_rendered_without_interpolation():
    config = render_config("https://hooks.example.test/officeflow", "ci-only-token")
    assert "type: Bearer" in config
    assert 'credentials: "ci-only-token"' in config


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.test/officeflow",
        "https://user:password@hooks.example.test/officeflow",
        "https://hooks.example.test/officeflow#fragment",
        "https://hooks.example.test:invalid/officeflow",
        "https://hooks.example.test/officeflow\nroute: injected",
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
        render_config("https://hooks.example.test/officeflow", "token\nforged")
