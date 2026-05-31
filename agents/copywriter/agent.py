import logging
import os
import pathlib

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

try:
    from .retry import GENERATE_CONTENT_CONFIG
except ImportError:
    from retry import GENERATE_CONTENT_CONFIG

load_dotenv()

logger = logging.getLogger("ai_creative_studio.copywriter")

_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "instagram-copywriting"
)
_skill_toolset = SkillToolset(skills=[_skill])

SYSTEM_INSTRUCTION = """You are an expert Social Media Copywriter specializing in Instagram content.

IMPORTANT: The conversation history above contains research from the Brand Strategist.
You MUST review their findings on audience insights, competitor analysis, and trending topics
before writing any copy. This context is your creative foundation.

You have access to an `instagram-copywriting` skill. Load it to get detailed platform
guidelines, caption formulas, and brand voice examples before writing.

Your task: Create exactly 3 Instagram caption variations covering different tonal registers.
Follow the output format defined in the skill exactly.

Each caption must include:
- The full caption text (with line breaks, emojis, and relevant hashtags)
- A label for the tonal register (e.g., "Inspirational", "Educational", "Playful")
- A strong call-to-action (CTA)
- 8-12 targeted hashtags

Format for each caption:

**Caption [N] - [Tonal Register]:**
[Full caption text]

[CTA line]

[Hashtag block]

---
"""

root_agent = Agent(
    name="copywriter",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    generate_content_config=GENERATE_CONTENT_CONFIG,
    tools=[_skill_toolset],
    instruction=SYSTEM_INSTRUCTION,
    description="Expert social media copywriter for creating engaging Instagram captions and copy",
)

logger.info("Copywriter agent created with instagram-copywriting skill")


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    load_dotenv()

    PORT = int(os.getenv("PORT", "8080"))
    HOST = os.getenv("HOST", "0.0.0.0")
    PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")
    PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", str(PORT)))
    PROTOCOL = os.getenv("PROTOCOL", "http")

    a2a_app = to_a2a(root_agent, host=PUBLIC_HOST, port=PUBLIC_PORT, protocol=PROTOCOL)

    logger.info(f"Starting Copywriter on {PROTOCOL}://{HOST}:{PORT}")
    logger.info(f"Agent card: {PROTOCOL}://{HOST}:{PORT}/.well-known/agent.json")

    uvicorn.run(a2a_app, host=HOST, port=PORT)
