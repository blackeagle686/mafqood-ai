from django.urls import path
from .views import ReportMissingPersonView

urlpatterns = [
    path('report/', ReportMissingPersonView.as_view(), name='report_missing'),
]
