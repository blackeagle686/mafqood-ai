import os
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import FaceSearchSerializer
from app.pipelines.search_pipeline import SearchPipeline
from utils.file_utils import cleanup_temp_file

class FaceSearchView(APIView):
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        serializer = FaceSearchSerializer(data=request.data)
        if serializer.is_valid():
            image = serializer.validated_data['file']
            n_results = serializer.validated_data['n_results']
            use_age_progression = serializer.validated_data['use_age_progression']
            sampling_rate = serializer.validated_data.get('sampling_rate', 15)
            
            # Save temp file
            ext = os.path.splitext(image.name)[1]
            temp_prefix = "search_video_" if ext.lower() in ['.mp4', '.avi', '.mov', '.mkv'] else "search_"
            
            is_video = False
            if ext.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
                is_video = True

            from django.conf import settings
            
            temp_path = os.path.join(settings.MEDIA_ROOT, f"{temp_prefix}{uuid.uuid4()}{ext}")
            
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            with open(temp_path, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            
            # Use pipeline
            result = {}
            pipeline = SearchPipeline()
            if is_video: # video search continuous frames
                result = pipeline.execute(
                    temp_path, 
                    n_results=n_results, 
                    use_age_progression=use_age_progression,
                    sampling_rate=sampling_rate
                )
            
            else: # image search no continuous frames
                result = pipeline.execute(
                    temp_path, 
                    n_results=n_results, 
                    use_age_progression=use_age_progression,
                )
            
            # Pre-calculate scores for template
            search_results = result.get('search_results', [])
            filtered_results = []
            for res in search_results:
                score = round(100 * max(0, 1 - res.get('distance', 1.0)), 1)
                if score > 40:
                    res['score'] = score
                    # Add image URL for the template
                    orig_path = res.get('metadata', {}).get('original_image', '')
                    if orig_path:
                        res['image_url'] = f"/media/{os.path.basename(orig_path)}"
                    filtered_results.append(res)
            
            search_results = filtered_results
            
            if request.accepted_renderer.format == 'html':
                 return Response({'results': search_results}, template_name='results.html')
                 
            return Response(result, status=status.HTTP_200_OK)
            
        if request.accepted_renderer.format == 'html':
             return Response({'errors': serializer.errors}, template_name='search.html')
             
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def seed_dummy_dna_profiles():
    from app.ai.models import Post, DNAProfile
    # Only seed if count is 0
    if DNAProfile.objects.count() == 0:
        # Ahmed: Child Profile
        p1, _ = Post.objects.get_or_create(
            post_id=901,
            defaults={
                'user_id': 'user_ahmed',
                'post_type': 0, # Lost
                'image_url': '/static/images/avatar_boy1.png',
                'is_resolved': False
            }
        )
        DNAProfile.objects.get_or_create(
            post=p1,
            defaults={
                'str_data': {
                    "D3S1358": [15, 16],
                    "vWA": [14, 17],
                    "TH01": [6, 9.3],
                    "FGA": [20, 24],
                    "AMEL": ["X", "Y"]
                },
                'gender': 'XY'
            }
        )

        # Sara: Sibling Profile
        p2, _ = Post.objects.get_or_create(
            post_id=902,
            defaults={
                'user_id': 'user_sara',
                'post_type': 0, # Lost
                'image_url': '/static/images/avatar_girl1.png',
                'is_resolved': False
            }
        )
        DNAProfile.objects.get_or_create(
            post=p2,
            defaults={
                'str_data': {
                    "D3S1358": [15, 16],
                    "vWA": [14, 18],
                    "TH01": [6, 7],
                    "FGA": [21, 25],
                    "AMEL": ["X", "X"]
                },
                'gender': 'XX'
            }
        )

        # Yusuf: Direct Profile
        p3, _ = Post.objects.get_or_create(
            post_id=903,
            defaults={
                'user_id': 'user_yusuf',
                'post_type': 0, # Lost
                'image_url': '/static/images/avatar_boy2.png',
                'is_resolved': False
            }
        )
        DNAProfile.objects.get_or_create(
            post=p3,
            defaults={
                'str_data': {
                    "D3S1358": [12, 14],
                    "vWA": [15, 16],
                    "TH01": [7, 8],
                    "FGA": [21, 23],
                    "AMEL": ["X", "Y"]
                },
                'gender': 'XY'
            }
        )


class DNASearchApiView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        seed_dummy_dna_profiles()
        
        str_data = request.data.get('strData')
        search_type = request.data.get('searchType', 'direct')
        min_overlap = int(request.data.get('minOverlap', 3))
        
        if not str_data:
            return Response({"error": "strData is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        from app.ai.models import DNAProfile
        from services.dna_search_service import DNASearchService
        
        db_profiles = DNAProfile.objects.filter(post__is_resolved=False)
        targets = []
        for profile in db_profiles:
            targets.append({
                "id": profile.post.post_id,
                "str_data": profile.str_data,
                "metadata": {
                    "userId": profile.post.user_id,
                    "postType": profile.post.post_type,
                    "gender": profile.gender,
                    "image_url": profile.post.image_url,
                    "name": "أحمد محمد" if profile.post.post_id == 901 else ("سارة علي" if profile.post.post_id == 902 else "يوسف خالد"),
                    "last_seen": "القاهرة" if profile.post.post_id == 901 else ("الإسكندرية" if profile.post.post_id == 902 else "الجيزة"),
                    "details": "طفل مفقود منذ عامين، تم مطابقة عينة DNA للأب للتحقق من صلة القرابة." if profile.post.post_id == 901 else ("طفلة مفقودة منذ ٦ أشهر، مطابقة عينات الأخوة." if profile.post.post_id == 902 else "طفل مفقود منذ ٣ أشهر، تطابق عينة مباشرة.")
                }
            })
            
        dna_service = DNASearchService()
        results = dna_service.search_profiles(
            query_profile=str_data,
            target_profiles=targets,
            search_type=search_type,
            min_overlap=min_overlap
        )
        
        for r in results:
            r['score'] = round(r['score'] * 100, 1)
            
        return Response({"isSuccess": True, "results": results}, status=status.HTTP_200_OK)

