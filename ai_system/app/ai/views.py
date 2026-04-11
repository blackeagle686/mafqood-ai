"""
Views for the AI (LLM) service endpoints.

Exposes two capabilities of the LLMService via DRF APIViews:
  - POST /api/ai/moderate/  → text content moderation
  - POST /api/ai/extract/   → entity extraction from social media posts (VLM)
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import os
from services.face_search_service import FaceSearchService
from .serializers import ModerateTextSerializer, ExtractEntitiesSerializer, MatchPostRequestSerializer
from infra.external.llm_client import LLMService
from utils.file_utils import download_remote_image, cleanup_temp_file

logger = logging.getLogger(__name__)

# Shared singletons
_llm_service = None
_face_service = None


def _get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def _get_face_service() -> FaceSearchService:
    global _face_service
    if _face_service is None:
        _face_service = FaceSearchService()
    return _face_service


class ModerateTextView(APIView):
    """
    POST /api/ai/moderate/

    Classify Arabic or English text for appropriateness using the LLM.
    Falls back to a static word-list when the LLM is unavailable.

    Request body (JSON):
        {
            "text": "النص المراد تصنيفه"
        }

    Response (200 OK):
        {
            "text":   "<original text>",
            "label":  "good" | "bad",
            "source": "llm" | "unavailable"
        }
    """

    def post(self, request):
        serializer = ModerateTextSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        text = serializer.validated_data["text"]

        try:
            llm = _get_llm_service()
            label = llm.classify_text_appropriateness(text)

            # classify_text_appropriateness returns "bad", "good", or "unknown"
            if label not in ("bad", "good"):
                # LLM returned ambiguous result — default to safe
                logger.warning("LLM returned ambiguous label '%s', defaulting to 'good'.", label)
                label = "good"
                source = "unavailable"
            else:
                source = "llm"

        except Exception as exc:
            logger.error("LLM moderation failed: %s", exc)
            return Response(
                {
                    "error": "LLM service is currently unavailable.",
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "text": text,
                "label": label,
                "source": source,
            },
            status=status.HTTP_200_OK,
        )


class ExtractEntitiesView(APIView):
    """
    POST /api/ai/extract/

    Extract structured entities (status, location, age, clothing) from an
    unstructured Arabic/English social media post using the VLM.

    Request body (JSON):
        {
            "text":      "طفل مفقود في القاهرة...",
            "image_url": "https://example.com/photo.jpg"  (optional)
        }

    Response (200 OK):
        {
            "status":          "missing" | "found",
            "location":        "Cairo" | "unknown",
            "age_estimation":  8 | null,
            "clothing":        "blue jacket" | "unknown",
            "input_text":      "<original text>",
            "image_used":      true | false
        }
    """

    def post(self, request):
        serializer = ExtractEntitiesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        text = serializer.validated_data["text"]
        image_url = serializer.validated_data.get("image_url")

        try:
            llm = _get_llm_service()
            entities = llm.extract_entities_from_post(text, image_url=image_url)

        except Exception as exc:
            logger.error("LLM entity extraction failed: %s", exc)
            return Response(
                {
                    "error": "LLM service is currently unavailable.",
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                **entities,
                "input_text": text,
                "image_used": image_url is not None,
            },
            status=status.HTTP_200_OK,
        )


class MatchPostView(APIView):
    """
    POST /api/ai/match-post/
    
    Connects with the base .NET backend system to evaluate a post for matches.
    """

    def post(self, request):
        serializer = MatchPostRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "isSuccess": False,
                "hasData": False,
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        post_id = serializer.validated_data["postId"]
        user_id = serializer.validated_data["userId"]
        image_url = serializer.validated_data["imageUrl"]
        post_type = serializer.validated_data["postType"]

        # Map postType: 0 -> "missing", 1 -> "found"
        status_str = "missing" if post_type == 0 else "found"

        # Resolve image path
        # If imageUrl is a URL, download it
        is_remote = image_url.startswith(("http://", "https://"))
        abs_image_path = None
        temp_path = None

        if is_remote:
            temp_path = download_remote_image(image_url)
            if not temp_path:
                return Response({
                    "isSuccess": False,
                    "hasData": False,
                    "error": f"Failed to download remote image: {image_url}"
                }, status=status.HTTP_400_BAD_REQUEST)
            abs_image_path = temp_path
        else:
            # Resolve local image path
            target_path = image_url
            if image_url.startswith("/uploads/"):
                target_path = image_url.replace("/uploads/", "")
            elif image_url.startswith("/media/"):
                target_path = image_url.replace("/media/", "")
            
            abs_image_path = os.path.join(settings.MEDIA_ROOT, target_path)
            
            if not os.path.exists(abs_image_path):
                # Fallback: Try to download from the production backend host
                backend_host = "https://mafqood.runasp.net"
                full_remote_url = f"{backend_host.rstrip('/')}/{image_url.lstrip('/')}"
                logger.info(f"Local file not found, attempting download from: {full_remote_url}")
                
                temp_path = download_remote_image(full_remote_url)
                if temp_path:
                    abs_image_path = temp_path
                    is_remote = True # Mark as remote for cleanup
                else:
                    # Final fallback check
                    if not os.path.exists(image_url):
                        return Response({
                            "isSuccess": False,
                            "hasData": False,
                            "error": f"Image file not found locally or at remote host: {image_url}"
                        }, status=status.HTTP_404_NOT_FOUND)
                    else:
                        abs_image_path = image_url

        try:
            face_service = _get_face_service()
            # If it's a temp path from download, we should clean it up AFTER matching
            # FaceSearchService.search_face_by_image has a cleanup param, 
            # but we'll handle it here to be explicit if needed or let it handle it.
            search_result = face_service.search_face_by_image(
                image_path=abs_image_path,
                n_results=5,
                cleanup=False, # We handle cleanup below to ensure it happens after response
                query_metadata={"status": status_str}
            )

            # Cleanup temp file if we downloaded it
            if is_remote and abs_image_path:
                cleanup_temp_file(abs_image_path)

            if search_result.get("status") == "error":
                return Response({
                    "isSuccess": False,
                    "hasData": False,
                    "error": search_result.get("message")
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            matches = []
            for res in search_result.get("search_results", []):
                # Try to get postId from metadata, fallback to face ID if it looks like an ID
                matched_id = res["metadata"].get("postId") or res["metadata"].get("post_id") or res["id"]
                
                matches.append({
                    "matchedPostId": matched_id,
                    "confidenceScore": res["similarity"] / 100.0 # Convert 0-100 to 0-1
                })

            response_data = {
                "isSuccess": True,
                "hasData": len(matches) > 0,
                "data": {
                    "userId": user_id,
                    "postId": post_id,
                    "matches": matches
                }
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.error("Match post evaluation failed: %s", exc)
            return Response({
                "isSuccess": False,
                "hasData": False,
                "error": str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
