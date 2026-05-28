import os
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import PersonReportSerializer
from app.pipelines.report_pipeline import ReportPipeline

class ReportMissingPersonView(APIView):
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        serializer = PersonReportSerializer(data=request.data)
        if serializer.is_valid():
            image = serializer.validated_data['file']
            name = serializer.validated_data['name']
            last_seen = serializer.validated_data['last_seen']
            details = serializer.validated_data['details']
            age = serializer.validated_data.get('age')
            lat = serializer.validated_data.get('lat')
            long = serializer.validated_data.get('long')
            dna_str_loci = serializer.validated_data.get('dna_str_loci')
            
            # Save file temporarily
            ext = os.path.splitext(image.name)[1]
            temp_filename = f"{uuid.uuid4()}{ext}"
            temp_path = os.path.join("temp_uploads", temp_filename)
            
            os.makedirs("temp_uploads", exist_ok=True)
            
            try:
                from PIL import Image
                img = Image.open(image)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Resize if larger than 1080 to optimize memory and processing time
                img.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
                img.save(temp_path, format='JPEG', quality=85)
            except Exception:
                # Fallback to writing chunks if Image processing fails
                image.seek(0)
                with open(temp_path, 'wb+') as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)
            
            abs_path = os.path.abspath(temp_path)
            metadata = {
                "name": name,
                "last_seen": last_seen,
                "details": details,
                "age": age,
                "lat": lat,
                "long": long,
                "dna_str_loci": dna_str_loci,
                "timestamp": str(uuid.uuid4()) # simple unique id for metadata
            }
            
            # Use pipeline
            pipeline = ReportPipeline()
            pipeline.execute(abs_path, metadata)
            
            success_msg = "Report received and is being processed."
            if request.accepted_renderer.format == 'html':
                return Response({'status': 'success', 'message': success_msg}, template_name='report.html')
                
            return Response({
                "status": "success",
                "message": success_msg
            }, status=status.HTTP_202_ACCEPTED)
            
        if request.accepted_renderer.format == 'html':
            return Response({'errors': serializer.errors}, template_name='report.html')
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
