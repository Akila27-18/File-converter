from django.urls import path
from . import views

urlpatterns = [
    path('merge/', views.merge, name='merge'),
    path('split/', views.split, name='split'),
    path('compress/', views.compress, name='compress'),
    path('share/<uuid:token>/', views.share_file, name='share_file'),
    path('pricing/', views.pricing, name='pricing'),
    path('my-documents/', views.my_documents, name='my_documents'),
]
