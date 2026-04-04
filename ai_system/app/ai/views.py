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

from infra.external.llm_client import LLMService
from .serializers import ModerateTextSerializer, ExtractEntitiesSerializer

logger = logging.getLogger(__name__)

# Shared singleton — avoids re-initialising the OpenAI client on every request
_llm_service = None


def _get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


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
