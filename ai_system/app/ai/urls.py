from django.urls import path
from . import views

urlpatterns = [
    path('moderate/', views.ModerateTextView.as_view(), name='ai_moderate'),
    path('extract/', views.ExtractEntitiesView.as_view(), name='ai_extract'),
    path('match-post/', views.MatchPostView.as_view(), name='ai_match_post'),
    path('posts/lost/', views.LostPeopleListView.as_view(), name='ai_posts_lost'),
    path('posts/found/', views.FoundPeopleListView.as_view(), name='ai_posts_found'),
    path('match/cross-check/', views.CrossMatchActionView.as_view(), name='ai_match_cross_check'),
    path('posts', views.ManagePostView.as_view(), name='ai_posts_manage'),
    path('posts/', views.ManagePostView.as_view(), name='ai_posts_manage_slash'),
    path('posts/mark-resolved', views.MarkPostResolvedView.as_view(), name='ai_posts_mark_resolved'),
    path('posts/mark-resolved/', views.MarkPostResolvedView.as_view(), name='ai_posts_mark_resolved_slash'),
    path('dna/posts', views.ManageDNAProfileView.as_view(), name='ai_dna_posts_manage'),
    path('dna/posts/', views.ManageDNAProfileView.as_view(), name='ai_dna_posts_manage_slash'),
    path('dna/search/', views.DNASearchView.as_view(), name='ai_dna_search'),
    path('agent/chat/', views.AgenticRAGView.as_view(), name='ai_agent_chat'),
]

