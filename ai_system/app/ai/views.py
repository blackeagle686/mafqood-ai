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
from services.dna_search_service import DNASearchService
from .serializers import (
    ModerateTextSerializer, 
    ExtractEntitiesSerializer, 
    MatchPostRequestSerializer,
    PostIntegrationSerializer,
    MarkResolvedIntegrationSerializer,
    DNAProfileIntegrationSerializer,
    DNASearchSerializer
)
from .models import Post, DNAProfile, DNAMatch
from .permissions import MafqoodAPIKeyAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from infra.external.llm_client import LLMService
from utils.file_utils import download_remote_image, cleanup_temp_file
from infra.celery.tasks import background_cross_match_task, background_dna_match_task
from infra.repositories.vector_db_repo import VectorDB

logger = logging.getLogger(__name__)


# Shared singletons
_llm_service = None
_face_service = None
_dna_service = None


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


def _get_dna_service() -> DNASearchService:
    global _dna_service
    if _dna_service is None:
        _dna_service = DNASearchService()
    return _dna_service


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
            "text":      "طفل اثر في القاهرة...",
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

        post_id = serializer.validated_data.get('postId')
        user_id = serializer.validated_data.get('userId')
        image_url = serializer.validated_data.get('imageUrl')
        post_type = serializer.validated_data.get('postType')

        # Map postType to status: 0 -> missing, 1 -> found
        status_str = "missing" if post_type == 0 else "found"
        
        query_metadata = {
            "postId": post_id,
            "userId": user_id,
            "status": status_str
        }

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
                query_metadata=query_metadata
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
                similarity = res.get("similarity", 0.0)
                if similarity < 60.0:
                    continue
                match_meta = res.get("metadata") or {}
                # Try to get postId from metadata, fallback to face ID if it looks like an ID
                matched_id = match_meta.get("postId") or match_meta.get("post_id") or res["id"]
                
                matches.append({
                    "matchedPostId": matched_id,
                    "confidenceScore": round(similarity / 100.0, 2)
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


class LostPeopleListView(APIView):
    """
    Endpoint to retrieve all indexed individuals marked as 'missing'.
    """
    def get(self, request):
        try:
            face_service = _get_face_service()
            limit = int(request.query_params.get('limit', 100))
            offset = int(request.query_params.get('offset', 0))
            
            people = face_service.get_people_by_status('missing', limit=limit, offset=offset)
            return Response({
                "isSuccess": True,
                "count": len(people),
                "data": people
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"isSuccess": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FoundPeopleListView(APIView):
    """
    Endpoint to retrieve all indexed individuals marked as 'found'.
    """
    def get(self, request):
        try:
            face_service = _get_face_service()
            limit = int(request.query_params.get('limit', 100))
            offset = int(request.query_params.get('offset', 0))
            
            people = face_service.get_people_by_status('found', limit=limit, offset=offset)
            return Response({
                "isSuccess": True,
                "count": len(people),
                "data": people
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"isSuccess": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CrossMatchActionView(APIView):
    """
    Endpoint to manually trigger the background cross-match reconciliation job.
    """
    def post(self, request):
        try:
            batch_size = int(request.data.get('batchSize', 50))
            # Trigger celery task
            background_cross_match_task.delay(batch_size=batch_size)
            
            return Response({
                "isSuccess": True,
                "message": "Background cross-match reconciliation task triggered."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"isSuccess": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ManagePostView(APIView):
    """
    Main integration endpoint for Create, Update, and Delete post operations from .NET.
    Protected by MafqoodAPIKeyAuthentication.
    """
    authentication_classes = [MafqoodAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        """
        Create Post:
        Saves to SQLite, downloads image, indexes in ChromaDB, matches and dispatches webhooks.
        """
        logger.info(f"Incoming POST to /api/ai/posts. Headers: {dict(request.headers)}. Data: {request.data}")
        serializer = PostIntegrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation failed for POST /api/ai/posts. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        userId = serializer.validated_data['userId']
        postId = serializer.validated_data['postId']
        postType = serializer.validated_data['postType']
        imageUrl = serializer.validated_data['imageUrl']

        # 1. Resolve image path (Download if remote URL)
        local_path = None
        if imageUrl.startswith(('http://', 'https://')):
            local_path = download_remote_image(imageUrl)
        else:
            # Check local file relative paths (for tests/local use)
            if os.path.exists(imageUrl):
                local_path = os.path.abspath(imageUrl)
            else:
                local_path = os.path.abspath(os.path.join(settings.BASE_DIR, imageUrl))

        if not local_path or not os.path.exists(local_path):
            return Response({
                "error": f"Failed to download or locate image: {imageUrl}"
            }, status=status.HTTP_400_BAD_REQUEST)

        face_service = _get_face_service()
        status_str = "missing" if postType == 0 else "found"

        # 2. Pre-ingestion check for Lost posts (postType == 0)
        pre_search_results = []
        if postType == 0:
            try:
                search_res = face_service.search_face_by_image(
                    local_path,
                    n_results=10,
                    cleanup=False
                )
                if search_res.get("status") == "success":
                    pre_search_results = search_res.get("search_results", [])
            except Exception as e:
                logger.error(f"Error in pre-ingestion check: {e}")

        # 3. Update/Create Post in local SQLite
        post, created = Post.objects.update_or_create(
            post_id=postId,
            defaults={
                'user_id': userId,
                'post_type': postType,
                'image_url': imageUrl,
                'is_resolved': False
            }
        )

        # 4. Index face embeddings in ChromaDB
        try:
            index_res = face_service.index_image(
                local_path,
                metadata={
                    "postId": postId,
                    "userId": userId,
                    "status": status_str,
                    "is_resolved": False,
                    "original_image": imageUrl
                }
            )
        except Exception as e:
            cleanup_temp_file(local_path)
            return Response({"error": f"Failed to index face: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 5. Cleanup temporary image file
        cleanup_temp_file(local_path)



        return Response({"isSuccess": True, "message": "Post successfully received and queued for matching."}, status=status.HTTP_200_OK)

    def put(self, request):
        """
        Update Post:
        Deletes old vector embeddings, updates SQLite record, indexes new image, and runs matching.
        """
        logger.info(f"Incoming PUT to /api/ai/posts. Headers: {dict(request.headers)}. Data: {request.data}")
        serializer = PostIntegrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation failed for PUT /api/ai/posts. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        postId = serializer.validated_data['postId']

        # Delete old embeddings from ChromaDB
        vdb = VectorDB()
        vectors = vdb.get_vectors(where={"postId": postId})
        if vectors and vectors.get("ids"):
            vdb.delete(ids=vectors["ids"])

        # Delegate to self.post for creating the updated instance & re-running matches
        return self.post(request)

    def delete(self, request):
        """
        Delete Post:
        Permanently removes post embeddings from ChromaDB and deletes the SQLite Post record.
        """
        logger.info(f"Incoming DELETE to /api/ai/posts. Headers: {dict(request.headers)}. Data: {request.data}")
        serializer = PostIntegrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation failed for DELETE /api/ai/posts. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        postId = serializer.validated_data['postId']

        # Delete embeddings from ChromaDB
        vdb = VectorDB()
        vectors = vdb.get_vectors(where={"postId": postId})
        if vectors and vectors.get("ids"):
            vdb.delete(ids=vectors["ids"])

        # Delete from SQLite
        Post.objects.filter(post_id=postId).delete()

        return Response({"isSuccess": True, "message": "Post deleted successfully."}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class MarkPostResolvedView(APIView):
    """
    Endpoint to confirm an item has been recovered.
    Flags SQLite record as is_resolved and deletes face embeddings from ChromaDB.
    """
    authentication_classes = [MafqoodAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        logger.info(f"Incoming POST to /api/ai/posts/mark-resolved. Headers: {dict(request.headers)}. Data: {request.data}")
        serializer = MarkResolvedIntegrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation failed for POST /api/ai/posts/mark-resolved. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        postId = serializer.validated_data['postId']

        try:
            post = Post.objects.get(post_id=postId)
            post.is_resolved = True
            post.save()
            
            # Delete embeddings from ChromaDB to stop including in future matching operations
            vdb = VectorDB()
            vectors = vdb.get_vectors(where={"postId": postId})
            if vectors and vectors.get("ids"):
                vdb.delete(ids=vectors["ids"])

            return Response({"isSuccess": True, "message": f"Post {postId} marked as resolved, vector index cleaned."}, status=status.HTTP_200_OK)
        except Post.DoesNotExist:
            return Response({"error": f"Post {postId} not found in local database."}, status=status.HTTP_404_NOT_FOUND)


class ManageDNAProfileView(APIView):
    """
    POST /api/ai/dna/posts
    Creates or updates the DNA STR profile associated with a post,
    then triggers background matching.

    DELETE /api/ai/dna/posts
    Deletes the DNA STR profile associated with a post.
    """
    authentication_classes = [MafqoodAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        logger.info(f"Incoming POST to /api/ai/dna/posts. Headers: {dict(request.headers)}")
        serializer = DNAProfileIntegrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation failed for POST /api/ai/dna/posts. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        postId = serializer.validated_data['postId']
        userId = serializer.validated_data['userId']
        postType = serializer.validated_data.get('postType', 0)
        str_data = serializer.validated_data['strData']
        gender = serializer.validated_data.get('gender')

        # Validate STR profile structure
        dna_service = _get_dna_service()
        is_valid, validation_errors = dna_service.validate_profile(str_data)
        if not is_valid:
            logger.error(f"Invalid STR data structure for postId {postId}. Errors: {validation_errors}")
            return Response({"error": "Invalid STR data structure.", "details": validation_errors}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create local Post object to link the DNAProfile to
        post, post_created = Post.objects.get_or_create(
            post_id=postId,
            defaults={
                'user_id': userId,
                'post_type': postType,
                'image_url': '',
                'is_resolved': False
            }
        )
        if not post_created and (post.user_id != userId or post.post_type != postType):
            post.user_id = userId
            post.post_type = postType
            post.save()

        dna_profile, created = DNAProfile.objects.update_or_create(
            post=post,
            defaults={
                'str_data': str_data,
                'gender': gender
            }
        )

        logger.info(f"DNA profile {'created' if created else 'updated'} for post {postId}. Triggering background matching task.")
        
        # Trigger Celery background matching task
        background_dna_match_task.delay(postId)

        return Response({
            "isSuccess": True,
            "message": f"DNA profile for post {postId} indexed successfully. Match process started in background."
        }, status=status.HTTP_202_ACCEPTED)

    def delete(self, request):
        logger.info(f"Incoming DELETE to /api/ai/dna/posts. Headers: {dict(request.headers)}. Params: {request.query_params}")
        postId = request.query_params.get('postId') or request.data.get('postId')
        if not postId:
            return Response({"error": "postId parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = DNAProfile.objects.get(post__post_id=postId)
            profile.delete()
            return Response({"isSuccess": True, "message": f"DNA Profile for post {postId} deleted successfully."}, status=status.HTTP_200_OK)
        except DNAProfile.DoesNotExist:
            return Response({"error": f"DNA Profile for post {postId} not found."}, status=status.HTTP_404_NOT_FOUND)


class DNASearchView(APIView):
    """
    POST /api/ai/dna/search/
    Submits a query DNA profile to find matching candidates in the database.
    """
    authentication_classes = [MafqoodAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        logger.info(f"Incoming POST to /api/ai/dna/search/. Headers: {dict(request.headers)}")
        serializer = DNASearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query_str_data = serializer.validated_data['strData']
        search_type = serializer.validated_data['searchType']
        min_overlap = serializer.validated_data.get('minOverlap', 5)

        # Retrieve all unresolved DNA profiles from the database
        db_profiles = DNAProfile.objects.filter(post__is_resolved=False)
        targets = []
        for profile in db_profiles:
            targets.append({
                "id": profile.post.post_id,
                "str_data": profile.str_data,
                "metadata": {
                    "userId": profile.post.user_id,
                    "postType": profile.post.post_type,
                    "gender": profile.gender
                }
            })

        dna_service = _get_dna_service()
        results = dna_service.search_profiles(
            query_profile=query_str_data,
            target_profiles=targets,
            search_type=search_type,
            min_overlap=min_overlap
        )

        return Response({
            "isSuccess": True,
            "results": results
        }, status=status.HTTP_200_OK)


from rest_framework.parsers import MultiPartParser, FormParser
from services.agentic_rag import AgenticRAGService
import uuid

class AgenticRAGView(APIView):
    """
    POST /api/ai/agent/chat/
    Agentic RAG endpoint that receives text, image, and/or DNA,
    and returns a response from the AI Agent.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = []
    
    def post(self, request):
        text_query = request.data.get('text', '')
        image_file = request.FILES.get('image')
        dna_data_str = request.data.get('dna')
        
        dna_data = None
        if dna_data_str:
            try:
                import json
                dna_data = json.loads(dna_data_str)
            except Exception as e:
                return Response({"error": "Invalid DNA JSON data"}, status=status.HTTP_400_BAD_REQUEST)
                
        image_path = None
        if image_file:
            import os
            from django.conf import settings
            ext = os.path.splitext(image_file.name)[1]
            temp_filename = f"agent_img_{uuid.uuid4()}{ext}"
            image_path = os.path.join(settings.MEDIA_ROOT, temp_filename)
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            with open(image_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
                    
        try:
            agent = AgenticRAGService()
            response_text = agent.process_query(text_query, image_path, dna_data)
            
            return Response({
                "isSuccess": True,
                "response": response_text
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Agentic RAG View Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



