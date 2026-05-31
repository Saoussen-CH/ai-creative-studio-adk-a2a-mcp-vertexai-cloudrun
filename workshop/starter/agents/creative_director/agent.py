import logging
import os

from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.plugins.logging_plugin import LoggingPlugin
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
try:
    from .retry import RETRY_CONFIG
    from .display_image_tool import display_image
    from .get_image_links_tool import get_image_links
except ImportError:
    from retry import RETRY_CONFIG
    from display_image_tool import display_image
    from get_image_links_tool import get_image_links

try:
    from .prompt import SYSTEM_INSTRUCTION_TEMPLATE
except ImportError:
    from prompt import SYSTEM_INSTRUCTION_TEMPLATE  # direct execution fallback

logger = logging.getLogger("ai_creative_studio.creative_director")
logger.setLevel(logging.INFO)


def create_creative_director():
    """
    Create the Creative Director orchestrator.
    Reads specialist URLs from environment variables at runtime.
    """
    # Read specialist URLs from environment
    copywriter_url = os.getenv("COPYWRITER_AGENT_URL")
    designer_url = os.getenv("DESIGNER_AGENT_URL")
    strategist_url = os.getenv("STRATEGIST_AGENT_URL")
    critic_url = os.getenv("CRITIC_AGENT_URL")
    pm_url = os.getenv("PM_AGENT_URL")

    available_agents_list = []
    agent_tools = [
        FunctionTool(func=display_image),
        FunctionTool(func=get_image_links),
    ]

    if strategist_url:
        available_agents_list.append(
            "- **brand_strategist**: Researches market trends, competitor brands, and audience insights"
        )
        agent_tools.append(AgentTool(agent=RemoteA2aAgent(
            name="brand_strategist",
            description="Brand strategist for market research and competitive insights",
            agent_card=f"{strategist_url}/.well-known/agent.json",
        )))

    if copywriter_url:
        available_agents_list.append(
            "- **copywriter**: Writes 3 Instagram caption variations with CTAs and hashtags"
        )
        agent_tools.append(AgentTool(agent=RemoteA2aAgent(
            name="copywriter",
            description="Expert social media copywriter for creating engaging Instagram captions",
            agent_card=f"{copywriter_url}/.well-known/agent.json",
        )))

    if designer_url:
        available_agents_list.append(
            "- **designer**: Generates visual concepts and real images via Imagen, returns gcs_uri values"
        )
        agent_tools.append(AgentTool(agent=RemoteA2aAgent(
            name="designer",
            description="Visual designer that generates Instagram images using Imagen",
            agent_card=f"{designer_url}/.well-known/agent.json",
        )))

    if critic_url:
        available_agents_list.append(
            "- **critic**: Reviews posts and visuals, scores them, and flags what needs revision"
        )
        agent_tools.append(AgentTool(agent=RemoteA2aAgent(
            name="critic",
            description="Creative critic for reviewing campaign materials and providing structured feedback",
            agent_card=f"{critic_url}/.well-known/agent.json",
        )))

    if pm_url:
        available_agents_list.append(
            "- **project_manager**: Creates campaign timeline, task list, and optionally persists to Notion"
        )
        agent_tools.append(AgentTool(agent=RemoteA2aAgent(
            name="project_manager",
            description="Project manager for creating campaign timelines and Notion project pages",
            agent_card=f"{pm_url}/.well-known/agent.json",
        )))

    available_agents_text = (
        "\n".join(available_agents_list)
        if available_agents_list
        else "No specialist agents configured. Set agent URLs in environment variables."
    )

    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(
        available_agents=available_agents_text
    )

    from google.genai import types
    generation_config = types.GenerateContentConfig(
        max_output_tokens=20000,
        temperature=0.2,
        http_options=types.HttpOptions(
            retry_options=RETRY_CONFIG,
            timeout=120_000,  # 120 second timeout for model calls
        ),
    )

    agent = Agent(
        name="creative_director",
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        description="Creative Director orchestrator that coordinates specialist agents",
        instruction=system_instruction,
        tools=agent_tools,
        generate_content_config=generation_config,
    )

    from google.adk.apps import App
    from google.adk.apps.app import EventsCompactionConfig
    from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
    from google.adk.models import Gemini

    compaction_config = EventsCompactionConfig(
        summarizer=LlmEventSummarizer(llm=Gemini(model_id=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))),
        compaction_interval=3,
        overlap_size=1,
    )
    app = App(
        name="creative_director",
        root_agent=agent,
        events_compaction_config=compaction_config,
        plugins=[LoggingPlugin()],
    )
    return agent, app


root_agent, root_app = create_creative_director()
