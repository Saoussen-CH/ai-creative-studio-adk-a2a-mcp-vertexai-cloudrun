"""Gemini retry config for handling 429 rate limits and transient errors.

Pay-as-you-go uses Dynamic Shared Quota, so 429s can fire when the shared pool
is busy. Application-level retries are required (the SDK does not enable them
by default). Embed RETRY_CONFIG inside the agent's GenerateContentConfig.
"""

from google.genai import types

RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,
    exp_base=2,
    initial_delay=5,
    http_status_codes=[429, 500, 503, 504],
)

