import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def main():
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or None
    if not api_key:
        raise SystemExit("LLM_API_KEY is missing from the project .env file.")

    try:
        models = OpenAI(api_key=api_key, base_url=base_url).models.list()
        for model in models.data:
            print(model.id)
    except Exception as error:
        status = getattr(error, "status_code", None)
        raise SystemExit(
            f"Could not list models ({type(error).__name__}, status={status})."
        ) from None


if __name__ == "__main__":
    main()
