from django.urls import path
from .views import checkout
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pricing.html")),
    path("checkout/<str:plan>/", checkout),
]
