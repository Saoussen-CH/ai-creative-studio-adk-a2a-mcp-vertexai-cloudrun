# Copyright 2026 Saoussen Chaabnia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Environment utilities for multi-agent deployment
Provides shared functions for loading, validating, and formatting environment variables
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    """
    Load and return environment variables from .env file

    Args:
        env_path: Optional path to .env file. If None, looks for .env in parent directory

    Returns:
        Dict with environment configuration
    """
    if env_path is None:
        # Look for .env in project root (one level up from deploy/)
        # __file__ = .../deploy/env_utils.py
        # parent = .../deploy
        # parent.parent = .../ (project root)
        env_path = Path(__file__).parent.parent / ".env"

    if env_path.exists():
        load_dotenv(env_path)

    # Support both naming conventions
    project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
        or os.getenv("PROJECT_ID")
    )
    # CLOUD_RUN_REGION is the Cloud Run deployment region (must be a real GCP region).
    # GOOGLE_CLOUD_LOCATION may be set to "global" for models only available globally —
    # keep them separate so model routing and Cloud Run region don't conflict.
    region = (
        os.getenv("CLOUD_RUN_REGION")
        or os.getenv("GCP_REGION")
        or os.getenv("LOCATION")
        or "us-central1"
    )

    return {
        "PROJECT_ID": project_id,
        "REGION": region,
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }


def validate_required_vars(config: dict[str, str]) -> bool:
    """
    Validate required environment variables are set

    Args:
        config: Dictionary of environment variables

    Returns:
        True if all required variables are present

    Raises:
        ValueError: If any required variable is missing
    """
    required = ["PROJECT_ID", "REGION"]
    missing = [key for key in required if not config.get(key)]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return True


def format_env_vars_for_orchestrator(agent_urls: dict[str, str]) -> dict[str, str]:
    """
    Format agent URLs as environment variables for orchestrator deployment

    Args:
        agent_urls: Dict mapping agent names to their Cloud Run URLs
                   e.g., {"brand-strategist": "https://...", "copywriter": "https://..."}

    Returns:
        Dict with standardized environment variable names for orchestrator
    """
    return {
        "STRATEGIST_AGENT_URL": agent_urls.get("brand-strategist", ""),
        "COPYWRITER_AGENT_URL": agent_urls.get("copywriter", ""),
        "DESIGNER_AGENT_URL": agent_urls.get("designer", ""),
        "CRITIC_AGENT_URL": agent_urls.get("critic", ""),
        "PM_AGENT_URL": agent_urls.get("project-manager", ""),
    }


def get_agent_name_mapping() -> dict[str, str]:
    """
    Get mapping between service names and environment variable keys

    Returns:
        Dict mapping service names to env var keys
    """
    return {
        "brand-strategist": "STRATEGIST_AGENT_URL",
        "copywriter": "COPYWRITER_AGENT_URL",
        "designer": "DESIGNER_AGENT_URL",
        "critic": "CRITIC_AGENT_URL",
        "project-manager": "PM_AGENT_URL",
    }


def update_env_file_with_urls(agent_urls: dict[str, str]) -> None:
    """
    Update the main .env file in-place, replacing agent URL values.
    All other settings (project ID, credentials, etc.) are preserved.

    Args:
        agent_urls: Dict mapping agent names to URLs
    """
    env_vars = format_env_vars_for_orchestrator(agent_urls)
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print(f"⚠️  .env not found at {env_path}, skipping in-place update")
        return

    lines = env_path.read_text().splitlines(keepends=True)
    updated = []
    replaced = set()

    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in env_vars and env_vars[key]:
            updated.append(f"{key}={env_vars[key]}\n")
            replaced.add(key)
        else:
            updated.append(line)

    # Append any keys that weren't already in the file
    for key, value in env_vars.items():
        if key not in replaced and value:
            updated.append(f"{key}={value}\n")

    env_path.write_text("".join(updated))
    print(f"✓ Updated agent URLs in {env_path}")


def save_urls_to_env_file(
    agent_urls: dict[str, str], output_file: str = ".env.specialists"
) -> None:
    """
    Save agent URLs to .env file for later use

    Args:
        agent_urls: Dict mapping agent names to URLs
        output_file: Path to output file (relative to project root)
    """
    env_vars = format_env_vars_for_orchestrator(agent_urls)

    # Write to file in project root
    project_root = Path(__file__).parent.parent
    output_path = project_root / output_file

    with open(output_path, "w") as f:
        f.write("# Specialist Agent URLs (auto-generated by deployment script)\n")
        f.write(f"# Generated at: {os.popen('date').read().strip()}\n\n")

        for key, value in env_vars.items():
            if value:
                f.write(f"{key}={value}\n")

    print(f"✓ Saved agent URLs to {output_path}")


if __name__ == "__main__":
    # Test the utilities
    print("Testing environment utilities...")

    config = load_env_file()
    print(f"\nLoaded config: {config}")

    try:
        validate_required_vars(config)
        print("✓ All required variables present")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")

    # Test URL formatting
    test_urls = {
        "brand-strategist": "https://brand-strategist-123.us-central1.run.app",
        "copywriter": "https://copywriter-123.us-central1.run.app",
        "designer": "https://designer-123.us-central1.run.app",
        "critic": "https://critic-123.us-central1.run.app",
        "project-manager": "https://project-manager-123.us-central1.run.app",
    }

    env_vars = format_env_vars_for_orchestrator(test_urls)
    print("\nFormatted environment variables:")
    for key, value in env_vars.items():
        print(f"  {key}={value}")
