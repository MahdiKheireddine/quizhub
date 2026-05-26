"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("quizzes.urls")),
    path("", include("attempts.urls")),
    path("u/", include("accounts.urls")),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    # Include django_browser_reload URLs only in DEBUG mode
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]

    # Error-page previews. Django only renders 404/500/403/400 templates when
    # DEBUG=False, so these routes let us check them while developing. Gated by
    # DEBUG; harmless in production.
    urlpatterns += [
        path("__preview/404/", lambda r: render(r, "404.html", status=404)),
        path("__preview/500/", lambda r: render(r, "500.html", status=500)),
        path("__preview/403/", lambda r: render(r, "403.html", status=403)),
        path("__preview/400/", lambda r: render(r, "400.html", status=400)),
    ]


# Explicit handler registration. Django finds the templates by convention
# anyway, but stating it explicitly here helps future readers see which
# templates back which error code.
handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"