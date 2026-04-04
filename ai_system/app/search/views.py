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

            temp_path = os.path.join("temp_uploads", f"{temp_prefix}{uuid.uuid4()}{ext}")
            
            os.makedirs("temp_uploads", exist_ok=True)
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
