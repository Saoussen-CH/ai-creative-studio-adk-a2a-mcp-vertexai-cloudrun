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

#!/usr/bin/env python3
"""
Deploy the Creative Director orchestrator to Gemini Enterprise Agent Platform Runtime.

Usage:
    python deploy_orchestrator.py --action deploy
    python deploy_orchestrator.py --action deploy --auto-deploy-specialists
    python deploy_orchestrator.py --action test --resource_name <resource_name>
    python deploy_orchestrator.py --action cleanup --resource_name <resource_name>
"""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

import vertexai
from dotenv import load_dotenv
from vertexai import Client, agent_engines

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID", "")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER") or subprocess.check_output(
    ["gcloud", "projects", "describe", PROJECT_ID, "--format=value(projectNumber)"],
    text=True,
).strip()
LOCATION = (
    os.getenv("CLOUD_RUN_REGION")
    or os.getenv("GCP_REGION")
    or os.getenv("LOCATION")
    or os.getenv("REGION")
    or "us-central1"
)
STAGING_BUCKET = f"gs://{PROJECT_ID}-agent-staging"
DISPLAY_NAME = "Creative Director"

COPYWRITER_URL = os.getenv("COPYWRITER_AGENT_URL", "")
DESIGNER_URL = os.getenv("DESIGNER_AGENT_URL", "")
STRATEGIST_URL = os.getenv("STRATEGIST_AGENT_URL", "")
CRITIC_URL = os.getenv("CRITIC_AGENT_URL", "")
PM_URL = os.getenv("PM_AGENT_URL", "")


def init_vertex_ai():
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )
    print("✓ Vertex AI initialized")
    print(f"  Project:  {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Staging:  {STAGING_BUCKET}")


def deploy_orchestrator(auto_deploy_specialists=False):
    """Deploy the Creative Director to Agent Platform Runtime."""

    if auto_deploy_specialists:
        print("\n" + "=" * 70)
        print("Deploying specialist agents first...")
        print("=" * 70)

        import env_utils
        from deploy_all_specialists import deploy_all_agents

        agent_urls = asyncio.run(deploy_all_agents(PROJECT_ID, LOCATION))

        if not agent_urls:
            print("\n❌ Specialist agent deployment failed — cannot continue.")
            sys.exit(1)

        env_vars_update = env_utils.format_env_vars_for_orchestrator(agent_urls)
        os.environ.update(env_vars_update)

        global COPYWRITER_URL, DESIGNER_URL, STRATEGIST_URL, CRITIC_URL, PM_URL
        COPYWRITER_URL = env_vars_update.get("COPYWRITER_AGENT_URL", "")
        DESIGNER_URL = env_vars_update.get("DESIGNER_AGENT_URL", "")
        STRATEGIST_URL = env_vars_update.get("STRATEGIST_AGENT_URL", "")
        CRITIC_URL = env_vars_update.get("CRITIC_AGENT_URL", "")
        PM_URL = env_vars_update.get("PM_AGENT_URL", "")

        print("\n✓ All specialist agents deployed:")
        for name, url in agent_urls.items():
            print(f"  • {name}: {url}")

    print("\n" + "=" * 70)
    print("Deploying Creative Director to Agent Platform Runtime")
    print("=" * 70)

    init_vertex_ai()

    sys.path.insert(0, str(project_root / "agents"))
    from creative_director.agent import root_app

    adk_app = agent_engines.AdkApp(
        app=root_app,
        enable_tracing=True,
    )

    print("\n⏳ Creating Agent Engine...")
    print(f"  COPYWRITER_AGENT_URL : {COPYWRITER_URL or '(not set)'}")
    print(f"  DESIGNER_AGENT_URL   : {DESIGNER_URL or '(not set)'}")
    print(f"  STRATEGIST_AGENT_URL : {STRATEGIST_URL or '(not set)'}")
    print(f"  CRITIC_AGENT_URL     : {CRITIC_URL or '(not set)'}")
    print(f"  PM_AGENT_URL         : {PM_URL or '(not set)'}")

    os.chdir(project_root / "agents")

    agent_engine_resource = agent_engines.create(
        agent_engine=adk_app,
        display_name=DISPLAY_NAME,
        requirements=[
            "google-cloud-aiplatform[agent_engines]>=1.132.0,<2.0.0",
            "google-adk[a2a]==1.31.1",
            "google-genai>=1.70.0",
            "google-cloud-storage>=2.10.0",
            "python-dotenv>=1.0.0",
            "pydantic>=2.0.0",
            "cloudpickle>=3.0.0",
        ],
        extra_packages=["creative_director"],
        env_vars={
            "COPYWRITER_AGENT_URL": COPYWRITER_URL,
            "DESIGNER_AGENT_URL": DESIGNER_URL,
            "STRATEGIST_AGENT_URL": STRATEGIST_URL,
            "CRITIC_AGENT_URL": CRITIC_URL,
            "PM_AGENT_URL": PM_URL,
            "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "GOOGLE_CLOUD_LOCATION": os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
            "SIGNING_SERVICE_ACCOUNT": f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
        },
    )

    resource_name = agent_engine_resource.resource_name
    agent_engine_id = resource_name.split("/")[-1]

    print("\n" + "=" * 70)
    print("✅ Creative Director deployed successfully!")
    print("=" * 70)
    print(f"\nResource Name: {resource_name}")
    print(f"Agent Engine ID: {agent_engine_id}")

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        lines = env_path.read_text().splitlines(keepends=True)
        updates = {
            "AGENT_ENGINE_RESOURCE_NAME": resource_name,
            "AGENT_ENGINE_ID": agent_engine_id,
        }
        updated = []
        replaced = set()
        for line in lines:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                updated.append(f"{key}={updates[key]}\n")
                replaced.add(key)
            else:
                updated.append(line)
        for key, value in updates.items():
            if key not in replaced:
                updated.append(f"{key}={value}\n")
        env_path.write_text("".join(updated))
        print("\n✓ .env updated with Agent Engine resource name and ID")

    print(
        f"\nView in Cloud Console:\n"
        f"https://console.cloud.google.com/vertex-ai/reasoning-engines?project={PROJECT_ID}"
    )
    return agent_engine_resource, resource_name


async def test_deployed_agent(resource_name: str):
    """Run a test campaign against the deployed agent."""
    print("\n" + "=" * 70)
    print("Testing deployed Creative Director")
    print("=" * 70)

    init_vertex_ai()

    remote_app = agent_engines.get(resource_name)
    print(f"✓ Connected to: {resource_name}")

    session = await remote_app.async_create_session(user_id="test_user")
    print(f"✓ Session: {session['id']}")

    test_query = (
        "Create a complete Instagram campaign for EcoFlow Smart Water Bottle "
        "(tracks hydration, keeps drinks cold 24h). "
        "Target: health-conscious millennials 25-35. "
        "Goal: brand awareness. Budget: $3,000."
    )
    print(f"\nQuery: {test_query}\n{'─' * 70}\n")

    async for event in remote_app.async_stream_query(
        user_id="test_user",
        session_id=session["id"],
        message=test_query,
    ):
        for part in event.get("content", {}).get("parts", []):
            if part.get("text") and not part.get("function_call"):
                print(part["text"], end="", flush=True)

    print(f"\n{'─' * 70}\n✓ Test complete.")


def cleanup_agent_engine(resource_name: str):
    """Delete the deployed Agent Engine resource."""
    print("\n" + "=" * 70)
    print("Deleting Agent Engine")
    print("=" * 70)
    print(f"\nResource: {resource_name}")

    confirmation = input("\n⚠️  Type 'yes' to confirm deletion: ")
    if confirmation.lower() != "yes":
        print("Cancelled.")
        return

    init_vertex_ai()

    client = Client(project=PROJECT_ID, location=LOCATION)
    client.agent_engines.delete(resource_name=resource_name)

    print("\n✓ Agent Engine deleted.")
    print("  Remove AGENT_ENGINE_RESOURCE_NAME and AGENT_ENGINE_ID from your .env.")


def main():
    parser = argparse.ArgumentParser(description="Deploy Creative Director to Agent Platform Runtime")
    parser.add_argument(
        "--action",
        choices=["deploy", "test", "cleanup"],
        default="deploy",
    )
    parser.add_argument("--resource_name", type=str)
    parser.add_argument(
        "--auto-deploy-specialists",
        action="store_true",
        help="Deploy all specialist agents to Cloud Run before deploying the orchestrator",
    )
    args = parser.parse_args()

    if args.action == "deploy":
        _, resource_name = deploy_orchestrator(
            auto_deploy_specialists=args.auto_deploy_specialists
        )
        print(f"\nTo test:   python {__file__} --action test --resource_name \"{resource_name}\"")
        print(f"To delete: python {__file__} --action cleanup --resource_name \"{resource_name}\"")

    elif args.action == "test":
        resource_name = args.resource_name or os.getenv("AGENT_ENGINE_RESOURCE_NAME")
        if not resource_name:
            print("ERROR: --resource_name required (or set AGENT_ENGINE_RESOURCE_NAME in .env)")
            sys.exit(1)
        asyncio.run(test_deployed_agent(resource_name))

    elif args.action == "cleanup":
        resource_name = args.resource_name or os.getenv("AGENT_ENGINE_RESOURCE_NAME")
        if not resource_name:
            print("ERROR: --resource_name required (or set AGENT_ENGINE_RESOURCE_NAME in .env)")
            sys.exit(1)
        cleanup_agent_engine(resource_name)


if __name__ == "__main__":
    main()
