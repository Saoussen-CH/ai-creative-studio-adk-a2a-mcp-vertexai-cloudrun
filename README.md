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
| **Creative Director** | Gemini 2.5 Flash | Orchestrates all specialists via A2A; `display_image`, `get_image_links` |
| **Brand Strategist** | Gemini 2.5 Flash | `google_search` for real-time market data |
| **Copywriter** | Gemini 2.5 Flash | ADK Skills (`instagram-copywriting`) |
| **Designer** | Gemini 2.5 Flash + Imagen | `generate_image` - calls Imagen 3, uploads to GCS |
| **Critic** | Gemini 2.5 Flash | `review_image` - multimodal review via `Part.from_uri` |
| **Project Manager** | Gemini 2.5 Flash | Notion MCP toolset (optional) |

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

## Tech Stack

- **[Google ADK](https://adk.dev) 1.31.1** - agent framework, A2A, Skills, MCP toolsets
- **Gemini 2.5 Flash** on Vertex AI - all text agents
- **Imagen 3** (`gemini-3.1-flash-image-preview`) - image generation
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
- APIs enabled: Vertex AI, Cloud Run, Cloud Storage, Secret Manager
- `gcloud` CLI authenticated (`gcloud auth application-default login`)

### Local Development

```bash
git clone https://github.com/Saoussen-CH/mas-a2a-gcp.git
cd mas-a2a-gcp
git checkout feature/full-implementation

uv sync
cp .env.example .env
# Fill in GOOGLE_CLOUD_PROJECT, GCS_IMAGES_BUCKET, and GEMINI_MODEL
```

Run locally with `adk web` (tests the Creative Director with all specialists as local agents):

```bash
uv run adk web agents --allow_origins='*'
```

### Deploy to GCP

Deploy all 5 specialist agents to Cloud Run:

```bash
uv run python deploy/deploy_all_specialists.py
```

Deploy the Creative Director orchestrator to Gemini Enterprise Agent Platform Runtime:

```bash
uv run python deploy/deploy_orchestrator.py
```

Run a full campaign against the deployed system:

```bash
uv run python run_campaign.py
```

## Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
CLOUD_RUN_REGION=us-central1
GCS_IMAGES_BUCKET=your-project-id-campaign-images
GEMINI_MODEL=gemini-2.5-flash
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image-preview

# Auto-populated by deployment scripts
COPYWRITER_AGENT_URL=
DESIGNER_AGENT_URL=
STRATEGIST_AGENT_URL=
CRITIC_AGENT_URL=
PM_AGENT_URL=
AGENT_ENGINE_ID=

# Optional - enables Notion project pages
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
