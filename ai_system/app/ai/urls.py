from django.urls import path
from .views import ModerateTextView, ExtractEntitiesView, MatchPostView

urlpatterns = [
    path('moderate/', ModerateTextView.as_view(), name='ai_moderate_text'),
    path('extract/', ExtractEntitiesView.as_view(), name='ai_extract_entities'),
    path('match-post/', MatchPostView.as_view(), name='ai_match_post'),
]
