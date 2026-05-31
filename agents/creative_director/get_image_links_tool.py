"""Image links tool: generates short-lived HTTPS URLs for GCS images."""
import os
import re
from datetime import timedelta


def get_image_links(gcs_uris: list[str]) -> dict:
    """
    Generate short-lived HTTPS links for GCS images so they can be opened in any browser.

    Call this once with all collected gcs_uri values before delivering the final campaign summary.

    Args:
        gcs_uris: List of GCS URIs (gs://bucket/path) from the Designer

    Returns:
        {"status": "success", "links": [{"concept": "...", "url": "https://..."}]}
        or {"status": "error", "error": "..."}
    """
    try:
        from google.cloud import storage as gcs
        import google.auth

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        client = gcs.Client(project=project_id)

        credentials, _ = google.auth.default()

        # Determine which SA email to sign as:
        # - On Cloud Run / Agent Engine: Compute Engine credentials carry a service_account_email
        # - Locally with user ADC: set SIGNING_SERVICE_ACCOUNT in .env
        sa_email = os.environ.get("SIGNING_SERVICE_ACCOUNT") or getattr(
            credentials, "service_account_email", None
        )

        # On Agent Runtime, service_account_email is "default" - resolve the real email
        # from the GCP metadata server.
        if sa_email == "default":
            import urllib.request
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
                headers={"Metadata-Flavor": "Google"},
            )
            sa_email = urllib.request.urlopen(req, timeout=2).read().decode()

        if sa_email:
            # Use IAM Sign Blob API - works for all credential types (Compute Engine,
            # Cloud Run, user ADC with impersonation). No private key needed.
            from google.auth import iam as google_auth_iam
            from google.auth.transport import requests as google_auth_requests
            from google.oauth2 import service_account as sa_module

            request = google_auth_requests.Request()
            credentials.refresh(request)

            signer = google_auth_iam.Signer(
                request=request,
                credentials=credentials,
                service_account_email=sa_email,
            )
            sign_credentials = sa_module.Credentials(
                signer=signer,
                service_account_email=sa_email,
                token_uri="https://oauth2.googleapis.com/token",
            )
            use_signed = True
        else:
            use_signed = False

        links = []
        for uri in gcs_uris:
            without_prefix = uri[len("gs://"):]
            bucket_name, blob_path = without_prefix.split("/", 1)
            blob = client.bucket(bucket_name).blob(blob_path)

            filename = blob_path.rsplit("/", 1)[-1]
            concept = re.sub(r"-[0-9a-f]{8}\.[^.]+$", "", filename)

            if use_signed:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(hours=1),
                    method="GET",
                    credentials=sign_credentials,
                )
            else:
                # No SA available - requires bucket public read access.
                # Set SIGNING_SERVICE_ACCOUNT in .env to enable signed URLs locally.
                url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"

            links.append({"concept": concept, "url": url})

        return {"status": "success", "links": links, "signed": use_signed}

    except Exception as e:
        return {"status": "error", "error": str(e)}
