from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView


class HealthCheckView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "ok"})


class LandingPageView(TemplateView):
    template_name = "landing.html"
