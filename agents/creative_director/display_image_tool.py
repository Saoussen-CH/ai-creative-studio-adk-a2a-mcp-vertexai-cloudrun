"""Artifact display tool: fetches a GCS image and saves it as an ADK artifact for inline rendering."""
import os

from google.adk.tools import ToolContext
from google.genai import types


async def display_image(gcs_uri: str, concept_name: str, tool_context: ToolContext) -> dict:
    """
    Fetch a generated image from GCS and save it as an artifact so it renders inline.

    Call this for each gcs_uri received from the Designer to show images in the local UI.

    Args:
        gcs_uri: GCS URI of the image (gs://bucket/path.png)
        concept_name: Short label for this image (e.g. "caption1_concept_a")

    Returns:
        {"status": "success", "concept_name": "..."} or {"status": "error", "error": "..."}
    """
    try:
        from google.cloud import storage as gcs

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        without_prefix = gcs_uri[len("gs://"):]
        bucket_name, blob_path = without_prefix.split("/", 1)

        client = gcs.Client(project=project_id)
        image_bytes = client.bucket(bucket_name).blob(blob_path).download_as_bytes()

        ext = blob_path.rsplit(".", 1)[-1].lower() if "." in blob_path else "png"
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")

        artifact = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(f"{concept_name}.{ext}", artifact)
        return {"status": "success", "concept_name": concept_name}

    except ValueError:
        # No artifact service configured (e.g. Cloud Run) - silently skip
        return {"status": "success", "concept_name": concept_name}
    except Exception as e:
        return {"status": "error", "concept_name": concept_name, "error": str(e)}
