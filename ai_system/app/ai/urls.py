from django.urls import path
from . import views

urlpatterns = [
    path('moderate/', views.ModerateTextView.as_view(), name='ai_moderate'),
    path('extract/', views.ExtractEntitiesView.as_view(), name='ai_extract'),
    path('match-post/', views.MatchPostView.as_view(), name='ai_match_post'),
    path('posts/lost/', views.LostPeopleListView.as_view(), name='ai_posts_lost'),
    path('posts/found/', views.FoundPeopleListView.as_view(), name='ai_posts_found'),
    path('match/cross-check/', views.CrossMatchActionView.as_view(), name='ai_match_cross_check'),
]
