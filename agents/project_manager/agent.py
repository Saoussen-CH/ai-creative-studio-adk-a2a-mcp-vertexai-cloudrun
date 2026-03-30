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
Project Manager Agent
Creates project timelines and tasks with Notion integration
"""

import datetime
import logging
import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

# Get logger for this agent
logger = logging.getLogger("ai_creative_studio.project_manager")


def get_system_instruction(database_id=None, tasks_database_id=None):
    """Generate system instruction with current date and Notion database IDs."""
    db_info = (
        f"Projects database ID: {database_id}\nTasks database ID: {tasks_database_id}"
        if database_id
        else "No Notion database configured."
    )

    return f"""You are a Project Manager specializing in creative campaign execution.

Today's date is {datetime.date.today().strftime("%B %d, %Y")}.
Use this as the starting point for all timelines.

{db_info}

Your goal: create a complete project plan for the campaign.

If Notion is configured, also persist the project and tasks to the Notion databases.
Use the available Notion tools to reason about what exists, discover the schema, and decide how to proceed.
Tool names follow the pattern `API-<operation>` — always use the exact hyphenated names from the tool manifest (e.g., `API-retrieve-a-database`, `API-post-page`). Never shorten or reformat them.
Call tools directly — never wrap them in `print()` and never prefix with `default_api.`

Constraints:
- Never set properties of type "people" or "person" (e.g., Owner, Assignee) — the Notion API does not allow integration tokens to assign users; skip these properties entirely
- Use only property names and values that actually exist in the schema you discover
- If any Notion operation fails, continue — the text timeline is the primary deliverable

Write your complete response AFTER all Notion operations are done (or have failed):

**Project Timeline:**
[Phase name] | [Start date] | [End date] | [Key activities]
Phase 1: Strategy & Research | [date] → [date]
Phase 2: Content Creation    | [date] → [date]
Phase 3: Review & Revision   | [date] → [date]
Phase 4: Launch & Monitoring | [date] → [date]

**Task List:**
| Task | Owner | Deadline | Status |
[list each task with realistic deadlines from today; set Owner to TBD]

**Budget Breakdown:**
[by category with approximate allocations]

**Milestones:**
[3-5 key checkpoints with dates]

**Notion Status:**
[What actually happened — e.g. "Project created (ID: xxx), 8 tasks linked" or "Notion not configured — text timeline only"]
Never repeat the timeline here.
"""


def create_project_manager_agent():
    """Create the Project Manager agent with Notion MCP integration"""
    notion_api_key     = os.getenv("NOTION_API_KEY")
    notion_database_id = os.getenv("NOTION_PROJECT_DATABASE_ID")
    notion_tasks_db_id = os.getenv("NOTION_TASKS_DATABASE_ID")

    if not notion_api_key or not notion_database_id:
        logger.warning(
            "NOTION_API_KEY or NOTION_PROJECT_DATABASE_ID not set - running without Notion integration"
        )
        return Agent(
            name="project_manager",
            model="gemini-2.5-flash",
            instruction=get_system_instruction(),
            description="Project manager that creates campaign timelines and task breakdowns",
        )
    else:
        logger.info(f"Configuring Notion MCP with database: {notion_database_id}")

        server_params = StdioServerParameters(
            command="notion-mcp-server",
            env={
                "NOTION_TOKEN": notion_api_key,
                "PATH": os.environ.get("PATH", ""),
            },
        )

        notion_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=server_params,
                timeout=30.0,
            )
        )

        return Agent(
            name="project_manager",
            model="gemini-2.5-flash",
            instruction=get_system_instruction(
                database_id=notion_database_id,
                tasks_database_id=notion_tasks_db_id,
            ),
            description="Project manager with Notion integration for task tracking",
            tools=[notion_toolset],
        )


# Create root_agent for A2A deployment
root_agent = create_project_manager_agent()


if __name__ == "__main__":
    import uvicorn
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    # Server listening configuration
    PORT = int(os.getenv("PORT", "8080"))
    HOST = os.getenv("HOST", "0.0.0.0")

    # Public-facing configuration for A2A agent card
    PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")
    PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", str(PORT)))
    PROTOCOL = os.getenv("PROTOCOL", "http")

    # Convert agent to A2A application
    a2a_app = to_a2a(root_agent, host=PUBLIC_HOST, port=PUBLIC_PORT, protocol=PROTOCOL)

    # Start server
    logger.info(f"🚀 Starting Project Manager A2A Server on {PROTOCOL}://{HOST}:{PORT}")
    logger.info(
        f"📋 Agent card available at: {PROTOCOL}://{HOST}:{PORT}/.well-known/agent-card.json"
    )
    logger.info(f"🌐 Public URL: {PROTOCOL}://{PUBLIC_HOST}:{PUBLIC_PORT}")

    uvicorn.run(a2a_app, host=HOST, port=PORT)
