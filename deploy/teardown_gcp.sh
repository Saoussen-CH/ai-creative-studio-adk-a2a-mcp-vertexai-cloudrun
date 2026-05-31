#!/bin/bash

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

# Teardown script for AI Creative Studio
# Deletes all Cloud Run services and the Agent Engine resource

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load .env if present
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-${PROJECT_ID:-}}"
REGION="${GCP_REGION:-${LOCATION:-us-central1}}"
AGENT_ENGINE_RESOURCE_NAME="${AGENT_ENGINE_RESOURCE_NAME:-}"

echo -e "${RED}=== AI Creative Studio — GCP Teardown ===${NC}\n"

# Validate gcloud
if ! command -v gcloud &>/dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Prompt for project ID if not set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}Enter your GCP Project ID:${NC}"
    read -r PROJECT_ID
fi

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID is required${NC}"
    exit 1
fi

echo -e "${YELLOW}The following resources will be deleted:${NC}"
echo -e "  Cloud Run services: brand-strategist, copywriter, designer, critic, project-manager"
echo -e "  Artifact Registry: cloud-run-source-deploy ($REGION)"
echo -e "  GCS buckets: gs://${PROJECT_ID}-campaign-images, gs://${PROJECT_ID}-agent-staging, gs://run-sources-${PROJECT_ID}-${REGION}"
echo -e "  Secret Manager secrets: notion-token, notion-project-db-id, notion-tasks-db-id (if they exist)"
if [ -n "$AGENT_ENGINE_RESOURCE_NAME" ]; then
    echo -e "  Agent Engine: $AGENT_ENGINE_RESOURCE_NAME"
else
    echo -e "  Agent Engine: (AGENT_ENGINE_RESOURCE_NAME not set — will be skipped)"
fi
echo -e "\n${RED}This action cannot be undone!${NC}"
echo -e "${YELLOW}Continue? (yes/no):${NC}"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${GREEN}Teardown cancelled${NC}"
    exit 0
fi

gcloud config set project "$PROJECT_ID" --quiet

# ─── Delete Cloud Run services ────────────────────────────────────────────────
echo -e "\n${YELLOW}Deleting Cloud Run services...${NC}"

for SVC in brand-strategist copywriter designer critic project-manager; do
    if gcloud run services describe "$SVC" \
        --region="$REGION" \
        --project="$PROJECT_ID" &>/dev/null; then
        gcloud run services delete "$SVC" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --quiet
        echo -e "  ${GREEN}✓ Deleted: $SVC${NC}"
    else
        echo -e "  ${YELLOW}Not found, skipping: $SVC${NC}"
    fi
done

# ─── Delete Agent Engine ───────────────────────────────────────────────────────
echo -e "\n${YELLOW}Deleting Agent Engine...${NC}"

if [ -z "$AGENT_ENGINE_RESOURCE_NAME" ]; then
    echo -e "  ${YELLOW}AGENT_ENGINE_RESOURCE_NAME not set — skipping Agent Engine deletion${NC}"
else
    python3 - <<PYEOF
import os, sys
try:
    import vertexai
except ImportError:
    print("  vertexai not installed — skipping Agent Engine deletion")
    sys.exit(0)

project  = os.environ.get("GCP_PROJECT_ID") or os.environ.get("PROJECT_ID", "")
location = os.environ.get("GCP_REGION") or os.environ.get("LOCATION", "us-central1")
resource = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "")

if not resource:
    print("  AGENT_ENGINE_RESOURCE_NAME not set — skipping")
    sys.exit(0)

try:
    client = vertexai.Client(project=project, location=location)
    client.agent_engines.delete(name=resource, force=True)
    print(f"  ✓ Agent Engine deleted: {resource}")
except Exception as e:
    print(f"  Warning: could not delete Agent Engine: {e}")
    print(f"  Delete manually: https://console.cloud.google.com/vertex-ai/reasoning-engines?project={project}")
PYEOF
fi

# ─── Delete Artifact Registry repository ─────────────────────────────────────
echo -e "\n${YELLOW}Deleting Artifact Registry repository...${NC}"

if gcloud artifacts repositories describe cloud-run-source-deploy \
    --location="$REGION" \
    --project="$PROJECT_ID" &>/dev/null; then
    gcloud artifacts repositories delete cloud-run-source-deploy \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --quiet
    echo -e "  ${GREEN}✓ Deleted: cloud-run-source-deploy${NC}"
else
    echo -e "  ${YELLOW}Not found, skipping: cloud-run-source-deploy${NC}"
fi

# ─── Delete GCS buckets ───────────────────────────────────────────────────────
echo -e "\n${YELLOW}Deleting GCS buckets...${NC}"

for BUCKET in \
    "gs://${PROJECT_ID}-campaign-images" \
    "gs://${PROJECT_ID}-agent-staging" \
    "gs://run-sources-${PROJECT_ID}-${REGION}"; do
    if gcloud storage buckets describe "$BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        gcloud storage rm -r "$BUCKET" --quiet
        echo -e "  ${GREEN}✓ Deleted: $BUCKET${NC}"
    else
        echo -e "  ${YELLOW}Not found, skipping: $BUCKET${NC}"
    fi
done

# ─── Delete Secret Manager secrets ───────────────────────────────────────────
echo -e "\n${YELLOW}Deleting Secret Manager secrets (Notion credentials)...${NC}"

for SECRET in notion-token notion-project-db-id notion-tasks-db-id; do
    if gcloud secrets describe "$SECRET" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets delete "$SECRET" --project="$PROJECT_ID" --quiet
        echo -e "  ${GREEN}✓ Deleted: $SECRET${NC}"
    else
        echo -e "  ${YELLOW}Not found, skipping: $SECRET${NC}"
    fi
done

# ─── Summary ──────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}=== Teardown Complete ===${NC}"
echo -e "\nVerify everything is removed:"
echo -e "  gcloud run services list --region=$REGION"
echo -e "  gcloud storage buckets list --project=$PROJECT_ID"
echo -e "  https://console.cloud.google.com/vertex-ai/reasoning-engines?project=$PROJECT_ID"
