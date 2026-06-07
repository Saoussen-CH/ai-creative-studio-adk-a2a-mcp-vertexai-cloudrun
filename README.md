# AI Creative Studio - Multi-Agent Instagram Campaign Generator

A fully implemented distributed multi-agent system built with **Google ADK**, the **A2A protocol**, **MCP**, and **Gemini on Vertex AI**. Five specialist AI agents collaborate to produce complete Instagram campaigns - from market research to image generation - coordinated by a Creative Director orchestrator.

---

## What It Does

Submit a campaign brief and the system autonomously:

1. **Researches** the market, competitors, and target audience (Brand Strategist + Google Search)
2. **Writes** 3 Instagram caption variations in different tonal registers (Copywriter + ADK Skills)
3. **Generates** real images for each caption via Imagen (Designer + GCS)
4. **Reviews** all outputs and requests revisions if quality scores are below threshold (Critic)
5. **Creates** a structured project timeline with tasks, budget, and milestones (Project Manager + optional Notion)

## Agents

| Agent | Model | Key Tools |
|-------|-------|-----------|
| **Creative Director** | Gemini 3 Flash Preview | Orchestrates all specialists via A2A; `display_image`, `get_image_links` |
| **Brand Strategist** | Gemini 3 Flash Preview | `google_search` for real-time market data |
| **Copywriter** | Gemini 3 Flash Preview | ADK Skills (`instagram-copywriting`) |
| **Designer** | Gemini 3 Flash Preview + Imagen | `generate_image` - calls Imagen 3, uploads to GCS |
| **Critic** | Gemini 3 Flash Preview | `review_image` - multimodal review via `Part.from_uri` |
| **Project Manager** | Gemini 3 Flash Preview | Notion MCP toolset (optional) |

## Architecture

```
User
 │
 ▼
Creative Director (ADK App + EventsCompactionConfig)
 │   ├── brand_strategist  (RemoteA2aAgent via A2A)
 │   ├── copywriter         (RemoteA2aAgent via A2A)
 │   ├── designer           (RemoteA2aAgent via A2A)
 │   ├── critic             (RemoteA2aAgent via A2A)
 │   └── project_manager    (RemoteA2aAgent via A2A)
 │
 ├── Each specialist runs as an independent Cloud Run service
 ├── Agents communicate over HTTPS via the A2A protocol
 ├── Images stored in GCS, reviewed multimodally by Critic
 └── Creative Director deployed to Gemini Enterprise Agent Platform Runtime
```

![System Architecture](diagrams/ai-creative-studio-architecture.png)

## Tech Stack

- **[Google ADK](https://adk.dev) 1.31.1** - agent framework, A2A, Skills, MCP toolsets
- **Gemini 3 Flash Preview** (`gemini-3-flash-preview`) on Vertex AI - all text agents
- **Imagen 3** (`gemini-3.1-flash-image`) - image generation
- **Cloud Run** - each specialist agent as an independent HTTPS service
- **Gemini Enterprise Agent Platform Runtime** - Creative Director orchestrator
- **Cloud Storage** - generated image storage
- **A2A Protocol** - inter-agent communication over HTTPS
- **MCP** (Model Context Protocol) - Notion integration for Project Manager
- **ADK Skills** - modular `instagram-copywriting` skill for Copywriter

## Repository Structure

```
agents/
  creative_director/     - orchestrator; EventsCompactionConfig; display_image + get_image_links tools
  brand_strategist/      - Google Search grounding; structured market research output
  copywriter/            - ADK Skills (instagram-copywriting); 3 caption tonal registers
    skills/
      instagram-copywriting/
  designer/              - Imagen 3 image generation; GCS upload; ADK artifact save
  critic/                - multimodal image review via Part.from_uri; structured JSON scoring
  project_manager/       - phase/task/budget timeline; Notion MCP (optional)
deploy/
  deploy_all_specialists.py   - deploys all 5 specialist agents to Cloud Run
  deploy_orchestrator.py      - deploys Creative Director to Agent Platform Runtime
  env_utils.py
  teardown_gcp.sh
pyproject.toml
.env.example
run_campaign.py          - run a campaign against a deployed Agent Platform Runtime instance
```

## Setup

### Prerequisites

- Google Cloud project with billing enabled
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) - `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `gcloud` CLI - authenticated with `gcloud auth login && gcloud auth application-default login`
- Node.js + npm - only required for local Notion integration

### Step 1 - Clone and install

```bash
git clone -b feature/full-implementation https://github.com/Saoussen-CH/ai-creative-studio-adk-a2a-mcp-vertexai-cloudrun.git
cd ai-creative-studio-adk-a2a-mcp-vertexai-cloudrun

uv sync
cp .env.example .env
```

### Step 2 - Set project variables

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
```

### Step 3 - Enable required GCP APIs

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project=${PROJECT_ID}
```

### Step 4 - Configure .env

> On macOS replace `sed -i` with `sed -i ''`

```bash
sed -i "s/GOOGLE_CLOUD_PROJECT=.*/GOOGLE_CLOUD_PROJECT=${PROJECT_ID}/" .env
sed -i "s/GOOGLE_CLOUD_PROJECT_NUMBER=.*/GOOGLE_CLOUD_PROJECT_NUMBER=${PROJECT_NUMBER}/" .env
sed -i "s/CLOUD_RUN_REGION=.*/CLOUD_RUN_REGION=${REGION}/" .env
sed -i "s/GOOGLE_CLOUD_LOCATION=.*/GOOGLE_CLOUD_LOCATION=global/" .env
sed -i "s/GCS_IMAGES_BUCKET=.*/GCS_IMAGES_BUCKET=${PROJECT_ID}-campaign-images/" .env
sed -i "s|SIGNING_SERVICE_ACCOUNT=.*|SIGNING_SERVICE_ACCOUNT=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com|" .env
```

### Step 5 - Create GCS buckets

```bash
# Bucket for generated images
gcloud storage buckets create gs://${PROJECT_ID}-campaign-images \
  --project=${PROJECT_ID} \
  --location=${REGION} \
  --uniform-bucket-level-access

# Staging bucket required by Agent Platform Runtime deployment
gcloud storage buckets create gs://${PROJECT_ID}-agent-staging \
  --project=${PROJECT_ID} \
  --location=${REGION} \
  --uniform-bucket-level-access
```

### Step 6 - Grant IAM permissions for signed URLs (local dev)

```bash
gcloud iam service-accounts add-iam-policy-binding \
  ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=${PROJECT_ID}
```

This allows your local user credentials to sign GCS URLs via the Compute Engine default service account.

### Step 7 - Run locally

```bash
uv run adk web agents --allow_origins='*'
```

This starts the Creative Director with all 5 specialists running as local in-process agents.

### Step 8 - Deploy to GCP

Deploy all 5 specialist agents to Cloud Run:

```bash
uv run python deploy/deploy_all_specialists.py
```

Deploy the Creative Director orchestrator to Agent Platform Runtime:

```bash
uv run python deploy/deploy_orchestrator.py
```

Run a campaign against the deployed system:

```bash
uv run python run_campaign.py
```

## Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_PROJECT_NUMBER=your-project-number
GOOGLE_CLOUD_LOCATION=global
CLOUD_RUN_REGION=us-central1
GCS_IMAGES_BUCKET=your-project-id-campaign-images
SIGNING_SERVICE_ACCOUNT=your-project-number-compute@developer.gserviceaccount.com
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
GOOGLE_GENAI_USE_VERTEXAI=1

# Auto-populated by deployment scripts
COPYWRITER_AGENT_URL=
DESIGNER_AGENT_URL=
STRATEGIST_AGENT_URL=
CRITIC_AGENT_URL=
PM_AGENT_URL=
AGENT_ENGINE_ID=
AGENT_ENGINE_RESOURCE_NAME=

# Optional - enables Notion project pages
# 1. Create an integration at https://www.notion.so/my-integrations
# 2. Share your databases with the integration
# 3. Install the MCP server locally: npm install -g @notionhq/notion-mcp-server@1.9.1
NOTION_TOKEN=
NOTION_PROJECT_DATABASE_ID=
NOTION_TASKS_DATABASE_ID=
```

## Image Visibility

Generated images are surfaced at three levels:

| Layer | How | Where it works |
|-------|-----|---------------|
| ADK artifacts | `save_artifact()` | `adk web` developer UI only |
| Signed HTTPS URLs | `get_image_links()` via GCS | Any browser, any UI |
| Notion embed | HTTPS links passed to Project Manager | Notion project page |

## Branches

| Branch | Description |
|--------|-------------|
| `workshop-final-release` | Codelab version with TODOs for participants to fill in |
| `feature/full-implementation` | This branch - complete working implementation, no placeholders |
