from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from accounts.views import HomeRedirectView
from nyo_dashboard.media_views import media_file_view
from nyo_dashboard.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeRedirectView.as_view(), name="home"),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("accounts/", include("accounts.urls")),
    path("members/", include("members.urls")),
    path("sessions/", include("sessions.urls")),
    path("finance/", include("finance.urls")),
    path("payments/", include("payments.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", media_file_view, name="media"),
    ]
