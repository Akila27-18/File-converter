from django.urls import path
from . import views

urlpatterns = [
    path("", views.tools, name="tools"),

    path("pricing/", views.pricing, name="pricing"),

    path("merge/", views.merge, name="merge"),
    path("split/", views.split, name="split"),
    path("compress/", views.compress, name="compress"),

    path("pdf-to-word/", views.pdf_to_word, name="pdf_to_word"),
    path("pdf-to-image/", views.pdf_to_image, name="pdf_to_image"),

    path("my-documents/", views.my_documents, name="my_documents"),

    # path("view/<uuid:token>/", views.view_pdf, name="view_pdf"),
    # path("download/<uuid:token>/", views.download_pdf, name="download_pdf"),
    # path("delete/<uuid:token>/", views.delete_pdf, name="delete_pdf"),

    path("share/<uuid:token>/", views.share_file, name="share_file"),
]
