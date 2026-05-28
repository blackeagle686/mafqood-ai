from django.urls import path
from .views import FaceSearchView, DNASearchApiView

urlpatterns = [
    path('face/', FaceSearchView.as_view(), name='face_search'),
    path('video/', FaceSearchView.as_view(), name='video_search'),
    path('dna/', DNASearchApiView.as_view(), name='dna_search_api'),
]
