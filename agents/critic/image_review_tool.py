"""Multimodal image review tool. Loads image from GCS via Part.from_uri()."""
import os
from typing import Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class _GeminiReview(BaseModel):
    """Internal schema used to force structured JSON output from Gemini."""
    score: int = Field(ge=1, le=10, description="Quality score from 1 to 10")
    approval_status: Literal["APPROVED", "NEEDS_REVISION"]
    what_works: str = Field(description="Specific visual strengths observed in the image")
    issues: str = Field(description="Specific problems identified, or 'None' if approved")
    suggestions: str = Field(description="Concrete improvements if NEEDS_REVISION, or 'None' if approved")


class ImageReviewResult(BaseModel):
    """Structured result returned to the Critic agent by the review_image tool."""
    status: Literal["success", "error"]
    concept_name: str
    score: Optional[int] = None
    approval_status: Optional[Literal["APPROVED", "NEEDS_REVISION"]] = None
    what_works: Optional[str] = None
    issues: Optional[str] = None
    suggestions: Optional[str] = None
    error: Optional[str] = None


def review_image(gcs_uri: str, concept_name: str, campaign_context: str) -> ImageReviewResult:
    """
    Review an image stored in GCS using Gemini multimodal.

    Vertex AI fetches the image from GCS server-side - no GCS credentials needed
    on the Critic container.

    Args:
        gcs_uri: GCS URI of the image (gs://bucket/path.png)
        concept_name: Name/label for this image concept
        campaign_context: Brief describing the campaign, brand voice, target audience

    Returns:
        ImageReviewResult with score (1-10), approval_status (APPROVED/NEEDS_REVISION),
        and structured feedback fields. On error, status="error" and error contains the message.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        client = genai.Client(vertexai=True, project=project_id, location=location)

        # Infer mime type from the GCS URI extension
        ext = gcs_uri.rsplit(".", 1)[-1].lower() if "." in gcs_uri else "png"
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")

        image_part = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)

        prompt = f"""You are reviewing an AI-generated image for an Instagram campaign.

Campaign context: {campaign_context}
Concept name: {concept_name}

Evaluate this image on:
- Visual quality and composition
- Brand alignment and audience fit
- Instagram platform suitability
- Visual-copy alignment potential

Scoring guide:
- 9-10: APPROVED (exceptional)
- 7-8:  APPROVED (good, minor polish only)
- 5-6:  NEEDS_REVISION (has potential but needs improvement)
- 1-4:  NEEDS_REVISION (significant issues)
"""

        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_schema=_GeminiReview,
                response_mime_type="application/json",
            ),
        )

        review = _GeminiReview.model_validate_json(response.text)
        return ImageReviewResult(status="success", concept_name=concept_name, **review.model_dump())

    except Exception as e:
        return ImageReviewResult(
            status="error",
            concept_name=concept_name,
            error=str(e),
        )
