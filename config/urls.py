from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from pdf_engine.views import tools

urlpatterns = [
    path('admin/', admin.site.urls),

    # Home / dashboard
    path('', tools, name='tools'),

    # PDF engine
    path('', include('pdf_engine.urls')),

    # Auth
    path('accounts/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
