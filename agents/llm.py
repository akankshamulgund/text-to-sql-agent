import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def chat(messages, tools=None):
    """Send a chat completion and retry only transient provider failures."""
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    base_url = os.getenv("LLM_BASE_URL") or None
    if not api_key or not model:
        raise RuntimeError("Set LLM_API_KEY and LLM_MODEL in the project .env file.")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as error:
        raise RuntimeError(
            f"Could not configure the LLM client ({type(error).__name__})."
        ) from None

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
            )
            return response.choices[0].message
        except Exception as error:
            status = getattr(error, "status_code", None)
            retryable = isinstance(error, (RateLimitError, APIConnectionError)) or (
                isinstance(error, APIStatusError) and status >= 500
            )
            if not retryable:
                detail = f"HTTP {status}" if status is not None else type(error).__name__
                raise RuntimeError(f"LLM request failed ({detail}).") from None
            if attempt == 2:
                detail = f"HTTP {status}" if status is not None else type(error).__name__
                raise RuntimeError(
                    f"LLM request failed after 3 attempts ({detail})."
                ) from None
            time.sleep(0.5 * (attempt + 1))
