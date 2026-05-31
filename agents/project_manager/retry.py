"""Gemini retry config for handling 429 rate limits and transient errors.

Pay-as-you-go uses Dynamic Shared Quota, so 429s can fire when the shared pool
is busy. Application-level retries are required (the SDK does not enable them
by default). Pass `generate_content_config=GENERATE_CONTENT_CONFIG` to every
Agent so each model call retries with exponential backoff before giving up.
"""

from google.genai import types

RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,
    exp_base=2,
    initial_delay=10,
    http_status_codes=[429, 500, 503, 504],
)

GENERATE_CONTENT_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=RETRY_CONFIG,
        timeout=120_000,  # 120 second timeout for model calls
    ),
)
