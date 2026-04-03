from django.shortcuts import render
from django.views.generic import TemplateView

class IndexView(TemplateView):
    template_name = "index.html"

class SearchView(TemplateView):
    template_name = "search.html"

class ReportView(TemplateView):
    template_name = "report.html"

class ResultsView(TemplateView):
    template_name = "results.html"

class VideoSearchView(TemplateView):
    template_name = "video_search.html"
