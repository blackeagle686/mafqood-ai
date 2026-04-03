from django.contrib import admin
from django.urls import path, include
from app.core_api.views import IndexView, SearchView, ReportView, ResultsView, VideoSearchView

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Page Views
    path('', IndexView.as_view(), name='index'),
    path('search/', SearchView.as_view(), name='search_page'),
    path('report/', ReportView.as_view(), name='report_page'),
    path('results/', ResultsView.as_view(), name='results_page'),
    path('video-search/', VideoSearchView.as_view(), name='video_search_page'),

    # API Endpoints
    path('api/people/', include('app.people.urls')),
    path('api/search/', include('app.search.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
