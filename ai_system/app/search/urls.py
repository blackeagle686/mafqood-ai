from django.urls import path
from .views import FaceSearchView

urlpatterns = [
    path('face/', FaceSearchView.as_view(), name='face_search'),
    path('video/', FaceSearchView.as_view(), name='video_search'), # Reusing FaceSearch for now or add VideoSearch
]
