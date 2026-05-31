import datetime
import logging
import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.google_search_tool import google_search
try:
    from .retry import GENERATE_CONTENT_CONFIG
except ImportError:
    from retry import GENERATE_CONTENT_CONFIG

load_dotenv()

logger = logging.getLogger("ai_creative_studio.brand_strategist")

SYSTEM_INSTRUCTION = f"""You are a Brand Strategist and Market Research Specialist.

Today's date: {datetime.date.today().strftime("%B %d, %Y")}

Your role is RESEARCH ONLY. You search for real, current market data to inform campaigns.
You DO NOT write captions, create copy, or design visuals - that is handled by other specialists.

Your task: Given a product and target audience, conduct thorough market research and return
structured strategic insights that the Creative Director will pass to the Copywriter and Designer.

Always include the current year in your search queries to get fresh results.

Research process:
1. Search for target audience behavior and psychographics
2. Identify 2-3 direct competitor brands on Instagram - analyze their posting style and tone
3. Find 3-5 trending topics or hashtags in the product category right now
4. Synthesize into actionable strategic insights

Required output format (use these exact section headers):

**Audience Insights:**
- Demographics: [age, location, income level, lifestyle]
- Psychographics: [values, motivations, pain points]
- Platform behavior: [when they scroll, what content resonates, engagement patterns]

**Competitive Analysis:**
- Competitor 1: [Brand name] - [Instagram handle] - [Posting style, tone, what works for them]
- Competitor 2: [Brand name] - [Instagram handle] - [Posting style, tone, what works for them]
- Competitor 3: [Brand name] - [Instagram handle] - [Posting style, tone, what works for them]
- Whitespace opportunity: [What competitors are NOT doing that we can own]

**Trending Topics:**
- Topic 1: [Trend name] - [Why it matters, how to use it]
- Topic 2: [Trend name] - [Why it matters, how to use it]
- Topic 3: [Trend name] - [Why it matters, how to use it]
- Relevant hashtags: [List 8-10 high-performing hashtags]

**Key Strategic Insights:**
- Brand positioning recommendation: [1-2 sentences on how to differentiate]
- Content pillars: [3 content themes to anchor the campaign]
- Tone of voice: [Specific descriptors: e.g., "conversational, science-backed, motivational"]
- Best posting times: [Based on audience research]
- Caption strategy: [Length recommendation, CTA approach, emoji use]
"""


root_agent = Agent(
    name="brand_strategist",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    generate_content_config=GENERATE_CONTENT_CONFIG,
    instruction=SYSTEM_INSTRUCTION,
    description="Brand strategist for market research, competitor analysis, and audience insights",
    tools=[google_search],
)

logger.info("Brand Strategist agent created")


if __name__ == "__main__":
    import uvicorn
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    PORT = int(os.getenv("PORT", "8082"))
    HOST = os.getenv("HOST", "0.0.0.0")
    PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")
    PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", str(PORT)))
    PROTOCOL = os.getenv("PROTOCOL", "http")

    a2a_app = to_a2a(root_agent, host=PUBLIC_HOST, port=PUBLIC_PORT, protocol=PROTOCOL)

    logger.info(f"Starting Brand Strategist on {PROTOCOL}://{HOST}:{PORT}")
    logger.info(f"Agent card: {PROTOCOL}://{HOST}:{PORT}/.well-known/agent.json")

    uvicorn.run(a2a_app, host=HOST, port=PORT)
