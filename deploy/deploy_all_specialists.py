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
Deploy all 5 specialist agents to Cloud Run and collect their URLs
Supports parallel deployment for faster execution
"""

import asyncio
import os
import sys
from pathlib import Path

# Import env_utils from same directory
sys.path.insert(0, str(Path(__file__).parent))
import env_utils

# Agent configuration for deployment
AGENTS = [
    {
        "name": "brand-strategist",
        "dir": "brand_strategist",
        "port": 8080,
    },
    {
        "name": "copywriter",
        "dir": "copywriter",
        "port": 8080,
    },
    {
        "name": "designer",
        "dir": "designer",
        "port": 8080,
    },
    {
        "name": "critic",
        "dir": "critic",
        "port": 8080,
    },
    {
        "name": "project-manager",
        "dir": "project_manager",
        "port": 8080,
    },
]


async def run_command_async(
    cmd: list[str], cwd: Path | None = None
) -> tuple[int, str, str]:
    """
    Run a command asynchronously

    Args:
        cmd: Command as list of strings
        cwd: Working directory for command

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
    )

    try:
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise


async def _add_secret_version(
    secret_id: str, value: str, project_id: str
) -> tuple[int, str, str]:
    """Add a version to an existing Secret Manager secret, passing the value via stdin."""
    process = await asyncio.create_subprocess_exec(
        "gcloud", "secrets", "versions", "add", secret_id,
        "--data-file=-",
        f"--project={project_id}",
        "--quiet",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate(input=value.encode())
        return process.returncode, stdout.decode(), stderr.decode()
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise


async def setup_notion_secrets(project_id: str) -> dict[str, str]:
    """
    Store Notion credentials in Secret Manager.
    Creates each secret if it doesn't exist, then adds a new version.

    Returns:
        {ENV_VAR_NAME: "secret-id:latest"} for --set-secrets,
        or empty dict if Notion credentials are not configured.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    notion_db_id = os.getenv("NOTION_PROJECT_DATABASE_ID")
    notion_tasks_db_id = os.getenv("NOTION_TASKS_DATABASE_ID")

    if not notion_token or not notion_db_id:
        return {}

    credentials = {
        "NOTION_TOKEN": ("notion-token", notion_token),
        "NOTION_PROJECT_DATABASE_ID": ("notion-project-db-id", notion_db_id),
    }
    if notion_tasks_db_id:
        credentials["NOTION_TASKS_DATABASE_ID"] = ("notion-tasks-db-id", notion_tasks_db_id)

    secret_refs = {}
    for env_var, (secret_id, value) in credentials.items():
        # Create secret (idempotent - ALREADY_EXISTS is not an error)
        await run_command_async([
            "gcloud", "secrets", "create", secret_id,
            f"--project={project_id}",
            "--replication-policy=automatic",
            "--quiet",
        ])
        # Add new version with the credential value
        returncode, _, stderr = await _add_secret_version(secret_id, value, project_id)
        if returncode == 0:
            secret_refs[env_var] = f"{secret_id}:latest"
            print(f"   ✓ {secret_id} stored in Secret Manager")
        else:
            print(f"   Warning: Could not store {secret_id}: {stderr.strip()}")

    return secret_refs


async def grant_pm_secret_access(project_id: str, secret_refs: dict[str, str]) -> None:
    """
    Grant the Project Manager Cloud Run service account
    roles/secretmanager.secretAccessor on each Notion secret.
    Uses the default Compute Engine SA (Cloud Run default).
    """
    if not secret_refs:
        return

    _, project_number, _ = await run_command_async([
        "gcloud", "projects", "describe", project_id,
        "--format=value(projectNumber)",
    ])
    sa_email = f"{project_number.strip()}-compute@developer.gserviceaccount.com"
    print(f"   Granting Secret Manager access to {sa_email}...")

    for _, secret_path in secret_refs.items():
        secret_id = secret_path.split(":")[0]
        returncode, _, stderr = await run_command_async([
            "gcloud", "secrets", "add-iam-policy-binding", secret_id,
            f"--member=serviceAccount:{sa_email}",
            "--role=roles/secretmanager.secretAccessor",
            f"--project={project_id}",
            "--quiet",
        ])
        if returncode == 0:
            print(f"   ✓ Access granted to {secret_id}")
        else:
            print(f"   Warning: Could not grant access to {secret_id}: {stderr.strip()}")


async def deploy_single_agent(
    agent_config: dict, project_id: str, region: str
) -> str | None:
    """
    Deploy a single agent to Cloud Run

    Args:
        agent_config: Agent configuration dict
        project_id: GCP project ID
        region: GCP region

    Returns:
        Agent URL or None if deployment failed
    """
    name = agent_config["name"]
    agent_dir = agent_config["dir"]

    print(f"🚀 Deploying {name}...")

    # Build Cloud Run deployment command
    agent_path = Path(__file__).parent.parent / "agents" / agent_dir

    # Build environment variables
    # GOOGLE_CLOUD_LOCATION controls model routing - may be "global" for preview
    # models. Read from env rather than using the Cloud Run deployment region.
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    model_location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    env_vars = (
        f"GOOGLE_GENAI_USE_VERTEXAI=true,"
        f"GOOGLE_CLOUD_PROJECT={project_id},"
        f"GOOGLE_CLOUD_LOCATION={model_location},"
        f"GEMINI_MODEL={gemini_model}"
    )

    # Add GCS bucket for image generation/review agents
    gcs_bucket = os.getenv("GCS_IMAGES_BUCKET", "")
    if gcs_bucket and name in ("designer", "critic"):
        print(f"   Adding GCS_IMAGES_BUCKET to {name}...")
        env_vars += f",GCS_IMAGES_BUCKET={gcs_bucket}"

    # Pass image model override to designer
    gemini_image_model = os.getenv("GEMINI_IMAGE_MODEL", "")
    if gemini_image_model and name == "designer":
        env_vars += f",GEMINI_IMAGE_MODEL={gemini_image_model}"

    # Store Notion credentials in Secret Manager for project-manager
    secret_refs: dict[str, str] = {}
    if name == "project-manager":
        if os.getenv("NOTION_TOKEN") and os.getenv("NOTION_PROJECT_DATABASE_ID"):
            print(f"   Storing Notion credentials in Secret Manager...")
            secret_refs = await setup_notion_secrets(project_id)
            if secret_refs:
                # Grant SA access before deploy so the service starts cleanly
                await grant_pm_secret_access(project_id, secret_refs)
        else:
            print(
                f"   Warning: NOTION_TOKEN or NOTION_PROJECT_DATABASE_ID not set"
                f" - {name} will work without Notion integration"
            )

    cmd = [
        "gcloud",
        "run",
        "deploy",
        name,
        "--source=.",
        "--port=8080",
        "--platform=managed",
        f"--region={region}",
        f"--project={project_id}",
        "--allow-unauthenticated",  # Allow public access to agent cards
        f"--set-env-vars={env_vars}",
        "--memory=1Gi",
        "--cpu=1",
        "--timeout=300",
        "--max-instances=10",
        "--min-instances=0",
        "--quiet",
    ]
    if secret_refs:
        secrets_flag = ",".join(f"{k}={v}" for k, v in secret_refs.items())
        cmd.append(f"--set-secrets={secrets_flag}")

    # Run deployment
    try:
        returncode, stdout, stderr = await run_command_async(cmd, cwd=agent_path)
    except Exception as e:
        print(f"❌ Failed to deploy {name}: {e}")
        return None

    if returncode != 0:
        print(f"❌ Failed to deploy {name}")
        print(f"   Error: {stderr}")
        return None

    print(f"✓ {name} deployed successfully")

    # Get service URL
    url = await get_service_url(name, project_id, region)

    if url:
        # Update A2A configuration
        await update_agent_a2a_config(name, url, project_id, region)

    # Grant Designer SA write access to the GCS images bucket
    if name == "designer" and url and os.getenv("GCS_IMAGES_BUCKET"):
        await grant_designer_gcs_access(name, project_id, region)

    return url


async def get_service_url(
    service_name: str, project_id: str, region: str
) -> str | None:
    """
    Get Cloud Run service URL after deployment

    Args:
        service_name: Name of the Cloud Run service
        project_id: GCP project ID
        region: GCP region

    Returns:
        Service URL or None if not found
    """
    cmd = [
        "gcloud",
        "run",
        "services",
        "describe",
        service_name,
        "--platform=managed",
        f"--region={region}",
        f"--project={project_id}",
        "--format=value(status.url)",
    ]

    returncode, stdout, stderr = await run_command_async(cmd)

    if returncode != 0:
        print(f"   Warning: Could not get URL for {service_name}")
        return None

    url = stdout.strip()
    print(f"   URL: {url}")
    return url


async def update_agent_a2a_config(
    service_name: str, url: str, project_id: str, region: str
) -> None:
    """
    Update deployed agent with A2A configuration (PUBLIC_HOST, PORT, PROTOCOL).
    Notion credentials are handled via Secret Manager at deploy time, not here.

    Args:
        service_name: Name of the Cloud Run service
        url: Service URL
        project_id: GCP project ID
        region: GCP region
    """
    # Extract PUBLIC_HOST from URL (remove https:// and trailing path)
    public_host = url.replace("https://", "").replace("http://", "").split("/")[0]

    print(f"   Updating A2A config for {service_name}...")

    # Build environment variables update
    env_vars_update = f"PUBLIC_HOST={public_host},PUBLIC_PORT=443,PROTOCOL=https"

    cmd = [
        "gcloud",
        "run",
        "services",
        "update",
        service_name,
        "--platform=managed",
        f"--region={region}",
        f"--project={project_id}",
        f"--update-env-vars={env_vars_update}",
        "--quiet",
    ]

    returncode, stdout, stderr = await run_command_async(cmd)

    if returncode == 0:
        print(f"   ✓ A2A config updated for {service_name}")
    else:
        print(f"   Warning: Could not update A2A config for {service_name}: {stderr}")


async def grant_designer_gcs_access(
    service_name: str, project_id: str, region: str
) -> None:
    """
    Grant the Designer Cloud Run service account storage.objectCreator on GCS bucket.
    Called automatically after designer deployment when GCS_IMAGES_BUCKET is set.
    """
    bucket = os.getenv("GCS_IMAGES_BUCKET")
    if not bucket:
        return

    print(f"   Granting GCS write access to {service_name} service account...")

    # Retrieve the service account email used by the Cloud Run service
    _, sa_email, _ = await run_command_async([
        "gcloud", "run", "services", "describe", service_name,
        "--platform=managed",
        f"--region={region}",
        f"--project={project_id}",
        "--format=value(spec.template.spec.serviceAccountName)",
    ])
    sa_email = sa_email.strip()

    # Fall back to compute default SA if no custom SA is configured
    if not sa_email:
        _, project_number, _ = await run_command_async([
            "gcloud", "projects", "describe", project_id,
            "--format=value(projectNumber)",
        ])
        sa_email = f"{project_number.strip()}-compute@developer.gserviceaccount.com"

    returncode, _, stderr = await run_command_async([
        "gcloud", "storage", "buckets", "add-iam-policy-binding",
        f"gs://{bucket}",
        f"--member=serviceAccount:{sa_email}",
        "--role=roles/storage.objectCreator",
        f"--project={project_id}",
    ])

    if returncode == 0:
        print(f"   ✓ GCS access granted to {sa_email}")
    else:
        print(f"   Warning: Could not grant GCS access: {stderr.strip()}")


async def deploy_all_agents(project_id: str, region: str) -> dict[str, str]:
    """
    Deploy all agents sequentially and collect their URLs.
    Sequential deployment avoids Cloud Build polling quota (60 req/min/user).
    """
    print("\n" + "=" * 70)
    print("Deploying all specialist agents to Cloud Run (sequential)")
    print("=" * 70 + "\n")

    # Pre-create the Artifact Registry repository
    print("⏳ Pre-creating Artifact Registry repository...")
    _, _, ar_err = await run_command_async([
        "gcloud", "artifacts", "repositories", "create", "cloud-run-source-deploy",
        "--repository-format=docker",
        f"--location={region}",
        f"--project={project_id}",
        "--quiet",
    ])
    if ar_err and "ALREADY_EXISTS" not in ar_err:
        print(f"   Warning: {ar_err.strip()}")
    else:
        print("   ✓ Artifact Registry repository ready\n")

    agent_urls = {}
    failed = []

    for i, agent in enumerate(AGENTS, 1):
        print(f"[{i}/{len(AGENTS)}] ", end="", flush=True)
        try:
            url = await deploy_single_agent(agent, project_id, region)
            if url:
                agent_urls[agent["name"]] = url
            else:
                failed.append(agent["name"])
        except Exception as e:
            print(f"⚠️  {agent['name']} raised an error: {e}")
            failed.append(agent["name"])

    print("\n" + "=" * 70)
    print(f"Deployment complete: {len(agent_urls)}/{len(AGENTS)} agents deployed")
    print("=" * 70)

    if agent_urls:
        print("\nDeployed:")
        for name, url in agent_urls.items():
            print(f"  ✓ {name}: {url}")

    if failed:
        print("\nFailed (re-run to retry):")
        for name in failed:
            print(f"  ❌ {name}")

    print()
    return agent_urls


async def main_async():
    """Async main function"""
    print("Multi-Agent Cloud Run Deployment\n")

    # Load environment configuration
    config = env_utils.load_env_file()

    try:
        env_utils.validate_required_vars(config)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease set the required environment variables in .env file:")
        print("  GCP_PROJECT_ID - Your Google Cloud project ID")
        print("  GCP_REGION - Deployment region (default: us-central1)")
        sys.exit(1)

    project_id = config["PROJECT_ID"]
    region = config["REGION"]

    print(f"Project: {project_id}")
    print(f"Region: {region}\n")

    # Check if gcloud is installed
    try:
        returncode, _, _ = await run_command_async(["gcloud", "version"])
        if returncode != 0:
            raise FileNotFoundError
    except FileNotFoundError:
        print("Error: gcloud CLI not found")
        print("Please install from: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)

    # Deploy all agents
    try:
        agent_urls = await deploy_all_agents(project_id, region)

        if not agent_urls:
            print("\n❌ No agents were deployed successfully")
            sys.exit(1)

        # Update .env in-place with Cloud Run URLs (replaces localhost values)
        env_utils.update_env_file_with_urls(agent_urls)

        print("\n✓ All specialist agents are ready!")
        print("  URLs written to .env")

        return agent_urls

    except Exception as e:
        print(f"\n❌ Error during deployment: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nDeployment interrupted. Already-deployed agents were not affected.")
        print("Re-run the script to deploy the remaining agents.")
        sys.exit(1)


if __name__ == "__main__":
    main()
