from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from src.config import Settings
from src.llm_client import LLMClient


def make_settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="test-model",
        github_token="token",
        target_repo="owner/repo",
    )


def make_mock_response(content: str) -> MagicMock:
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


def make_rate_limit_error() -> RateLimitError:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(429, request=req)
    return RateLimitError(message="rate limited", response=resp, body={})


def make_api_status_error(status_code: int) -> APIStatusError:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(status_code, request=req)
    return APIStatusError(message=f"error {status_code}", response=resp, body={})


def test_chat_success():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.return_value = make_mock_response("hello")

    result = client.chat("system", "user")
    assert result == "hello"


def test_chat_retry_on_rate_limit():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.side_effect = [
        make_rate_limit_error(),
        make_mock_response("ok after retry"),
    ]

    with patch("src.llm_client.time.sleep") as mock_sleep:
        result = client.chat("system", "user")

    assert result == "ok after retry"
    mock_sleep.assert_called_once_with(2)


def test_chat_retry_on_500():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.side_effect = [
        make_api_status_error(503),
        make_mock_response("ok"),
    ]

    with patch("src.llm_client.time.sleep"):
        result = client.chat("system", "user")

    assert result == "ok"


def test_chat_no_retry_on_4xx():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.side_effect = make_api_status_error(400)

    with pytest.raises(APIStatusError):
        client.chat("system", "user")

    assert client.client.chat.completions.create.call_count == 1


def test_chat_raises_after_max_retries():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.side_effect = make_rate_limit_error()

    with patch("src.llm_client.time.sleep"):
        with pytest.raises(RateLimitError):
            client.chat("system", "user")

    assert client.client.chat.completions.create.call_count == 4  # 1 initial + 3 retries


def test_chat_exponential_backoff():
    client = LLMClient(make_settings())
    client.client = MagicMock()
    client.client.chat.completions.create.side_effect = [
        make_rate_limit_error(),
        make_rate_limit_error(),
        make_mock_response("ok"),
    ]

    with patch("src.llm_client.time.sleep") as mock_sleep:
        result = client.chat("system", "user")

    assert result == "ok"
    calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert calls == [2, 4]
