import logging
import time

from openai import APIStatusError, OpenAI, RateLimitError

from src.config import Settings

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [2, 4, 8]


class LLMClient:
    def __init__(self, settings: Settings):
        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.model = settings.openai_model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                )
                return response.choices[0].message.content or ""
            except RateLimitError:
                if attempt == len(_RETRY_DELAYS):
                    raise
                delay = _RETRY_DELAYS[attempt]
                logger.warning("LLM rate limited, retry %d in %ds", attempt + 1, delay)
                time.sleep(delay)
            except APIStatusError as e:
                if attempt == len(_RETRY_DELAYS) or e.status_code < 500:
                    raise
                delay = _RETRY_DELAYS[attempt]
                logger.warning("LLM API error %d, retry %d in %ds", e.status_code, attempt + 1, delay)
                time.sleep(delay)
        raise RuntimeError("unreachable")
