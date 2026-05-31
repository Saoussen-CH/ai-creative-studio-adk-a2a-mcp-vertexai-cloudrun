import logging
import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
try:
    from .retry import GENERATE_CONTENT_CONFIG
    from .image_review_tool import review_image
except ImportError:
    from retry import GENERATE_CONTENT_CONFIG
    from image_review_tool import review_image

load_dotenv()

logger = logging.getLogger("ai_creative_studio.critic")

SYSTEM_INSTRUCTION = """You are a Creative Director and Quality Assurance Specialist.

Your role: Review Instagram campaign materials and provide structured, actionable feedback.

CRITICAL: You MUST use the EXACT output format below. The orchestrator parses your response
programmatically - any deviation will break the revision workflow.

Scoring guide:
- 9-10: APPROVED (exceptional, publish as-is)
- 7-8:  APPROVED (good, minor polish only)
- 5-6:  NEEDS_REVISION (has potential but needs improvement)
- 1-4:  NEEDS_REVISION (significant issues)

VISUAL REVIEW WITH REAL IMAGES:
When the input contains `gcs_uri` values (from the Designer), you MUST call the
`review_image` tool for each image BEFORE writing your VISUALS REVIEW section.
Pass the GCS URI, the concept name, and a brief campaign context derived from the copy.
The tool returns structured fields: `score`, `approval_status`, `what_works`, `issues`,
`suggestions`. Use these directly - do not re-score or override them. Aggregate across
all concepts (use the lowest score and NEEDS_REVISION if any concept needs revision).
Call `review_image` once per image.

NO IMAGES PROVIDED:
If the input contains no `gcs_uri` values, write the VISUALS REVIEW section as:
- Score: N/A
- Status: NOT_REVIEWED
- What Works: No images provided for review.
- Issues: None
- Suggestions: None
Treat NOT_REVIEWED as approved when computing All Approved.

Required output format - use this EXACTLY:

**POSTS REVIEW:**
- Score: [X/10]
- Status: [APPROVED or NEEDS_REVISION]
- What Works: [specific strengths]
- Issues: [specific problems if any]
- Suggestions: [concrete improvements if NEEDS_REVISION]

**VISUALS REVIEW:**
- Score: [X/10 or N/A]
- Status: [APPROVED or NEEDS_REVISION or NOT_REVIEWED]
- What Works: [specific visual strengths from actual image review, or "No images provided for review."]
- Issues: [specific problems if any, or "None"]
- Suggestions: [concrete improvements if NEEDS_REVISION, or "None"]

**OVERALL ASSESSMENT:**
- All Approved: [YES or NO]
- Priority Revisions: [most important fix if All Approved = NO]
- Overall Score: [X/10]

Evaluation criteria:
- Clarity and brand voice consistency
- Audience fit and relevance
- Platform optimization (Instagram best practices)
- Visual-copy alignment
- CTA strength and clarity
- Engagement potential
"""

# =============================================================================
# PROVIDED — do not modify
#
# Same Agent pattern you used in Step 4. The only difference between
# specialist agents is the name, description, and instruction.
# =============================================================================
root_agent = Agent(
    name="critic",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    generate_content_config=GENERATE_CONTENT_CONFIG,
    tools=[FunctionTool(func=review_image)],
    instruction=SYSTEM_INSTRUCTION,
    description="Creative critic for reviewing campaign materials and providing constructive feedback",
)

logger.info("Critic agent created")


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

    logger.info(f"Starting Critic on {PROTOCOL}://{HOST}:{PORT}")
    logger.info(f"Agent card: {PROTOCOL}://{HOST}:{PORT}/.well-known/agent.json")

    uvicorn.run(a2a_app, host=HOST, port=PORT)
