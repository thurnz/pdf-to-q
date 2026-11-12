#!/usr/bin/env python3
"""List available Gemini models for the configured GEMINI_API_KEY."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from google import genai  # noqa: E402
from google.genai import errors  # noqa: E402

from app.config import Settings  # noqa: E402


def main() -> None:
    # Attempt to load settings; if gemini_model is not set yet, use a placeholder
    try:
        settings = Settings()
    except Exception:
        settings = Settings(gemini_model="placeholder")

    if not settings.gemini_api_key:
        print(
            "Error: GEMINI_API_KEY is not configured in .env or environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Fetching models available to your Gemini API key...\n")
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        pager = client.models.list()
        found_count = 0

        for model in pager:
            name = getattr(model, "name", "")
            display_name = getattr(model, "display_name", "")
            if name:
                found_count += 1
                # Show both canonical name and display name if available
                if display_name:
                    print(f"  • {name}  ({display_name})")
                else:
                    print(f"  • {name}")

        if found_count == 0:
            print("No models returned by API.")
        else:
            print(f"\nTotal: {found_count} model(s) available.")
            print(
                "Set GEMINI_MODEL in .env to one of the above names (e.g. gemini-2.5-flash)."
            )

    except errors.APIError as exc:
        print(f"API Error ({exc.code}): {exc.message or exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error communicating with Gemini: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
