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
            
            # Save file temporarily
            ext = os.path.splitext(image.name)[1]
            temp_filename = f"{uuid.uuid4()}{ext}"
            temp_path = os.path.join("temp_uploads", temp_filename)
            
            os.makedirs("temp_uploads", exist_ok=True)
            with open(temp_path, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            
            abs_path = os.path.abspath(temp_path)
            metadata = {
                "name": name,
                "last_seen": last_seen,
                "details": details,
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
