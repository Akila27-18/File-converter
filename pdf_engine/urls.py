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
    path("image-to-pdf/", views.image_to_pdf, name="image_to_pdf"),
    path("word-to-pdf/", views.word_to_pdf, name="word_to_pdf"),

    path("my-documents/", views.my_documents, name="my_documents"),
    path("unlock-pdf/", views.unlock_pdf_view, name="unlock_pdf_view"),

    path("pdf-to-excel/", views.pdf_to_excel, name="pdf_to_excel"),
    path("excel-to-pdf/", views.excel_to_pdf, name="excel_to_pdf"),


    path("view/<uuid:token>/", views.view_pdf, name="view_pdf"),
    path("download/<uuid:token>/", views.download_pdf, name="download_pdf"),
    path("delete/<uuid:token>/", views.delete_pdf, name="delete_pdf"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("share/<uuid:token>/", views.share_file, name="share_file"),
]
