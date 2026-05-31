"""
Run a campaign through the deployed Creative Director on Agent Engine.
Usage: uv run run_campaign.py
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import Client

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID") or os.getenv("PROJECT_ID")
LOCATION = os.getenv("CLOUD_RUN_REGION") or os.getenv("GCP_REGION") or os.getenv("LOCATION", "us-central1")

vertexai.init(project=PROJECT_ID, location=LOCATION)
client = Client(project=PROJECT_ID, location=LOCATION)

resource_name = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/"
    f"reasoningEngines/{os.getenv('AGENT_ENGINE_ID')}"
)

agent_engine = client.agent_engines.get(name=resource_name)
session = agent_engine.create_session(user_id="workshop-user")
print(f"Session: {session['id']}\n")

campaign_brief = """
Create a complete Instagram campaign for:
- Product: EcoFlow Smart Water Bottle (tracks hydration, keeps drinks cold 24h)
- Target Audience: Health-conscious millennials, 25-35 years old
- Platform: Instagram
- Goal: Brand awareness + drive website traffic
- Brand Voice: Motivational, clean, science-backed
- Budget: $3,000
- Timeline: Launch in 2 weeks
"""

for event in agent_engine.stream_query(
    user_id="workshop-user",
    session_id=session["id"],
    message=campaign_brief,
):
    if "content" in event and "parts" in event["content"]:
        for part in event["content"]["parts"]:
            if "text" in part:
                print(part["text"], end="", flush=True)
