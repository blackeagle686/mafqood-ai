from django.urls import path
from .views import ModerateTextView, ExtractEntitiesView

urlpatterns = [
    path('moderate/', ModerateTextView.as_view(), name='ai_moderate_text'),
    path('extract/', ExtractEntitiesView.as_view(), name='ai_extract_entities'),
]
