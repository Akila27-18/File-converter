from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.utils import timezone
from datetime import timedelta
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import tempfile, os, zipfile

from accounts.models import UserProfile
from .models import SharedFile
from django.core.mail import send_mail
from docx import Document
from pdf2image import convert_from_path
import uuid

# =====================================================
# UTILITIES
# =====================================================

def pdf_response(path, filename, inline=False):
    with open(path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/pdf")
        response["Content-Disposition"] = (
            "inline" if inline else "attachment"
        ) + f'; filename="{filename}"'
        return response


def parse_pages(pages_str):
    pages = set()
    for part in pages_str.split(","):
        if "-" in part:
            start, end = part.split("-")
            pages.update(range(int(start) - 1, int(end)))
        else:
            pages.add(int(part) - 1)
    return sorted(pages)


# =====================================================
# DASHBOARD / STATIC PAGES
# =====================================================

def tools(request):
    return render(request, "tools.html")


def pricing(request):
    return render(request, "pricing.html")


@login_required
def my_documents(request):
    files = SharedFile.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "my_documents.html", {
        "files": files,
        "now": timezone.now()
    })


# =====================================================
# PDF ACTIONS
# =====================================================

@login_required
def merge(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        files = request.FILES.getlist("files")

        if len(files) < 2:
            messages.error(request, "Select at least 2 PDFs.")
            return redirect("merge")

        merger = PdfMerger()
        for f in files:
            merger.append(f)

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        merger.write(temp.name)
        merger.close()

        with open(temp.name, "rb") as f:
            shared = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=profile.share_days())
            )
            shared.file.save("merged.pdf", File(f))

        os.remove(temp.name)
        profile.increment()

        return render(request, "merge.html", {
            "share_url": request.build_absolute_uri(
                f"/share/{shared.token}/"
            )
        })

    return render(request, "merge.html")


@login_required
def split(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES.get("files")

        reader = PdfReader(pdf)
        writer = PdfWriter()

        mode = request.POST.get("mode")
        pages = request.POST.get("pages", "")

        if mode == "custom" and pages:
            for part in pages.split(","):
                if "-" in part:
                    s, e = part.split("-")
                    for i in range(int(s)-1, int(e)):
                        writer.add_page(reader.pages[i])
                else:
                    writer.add_page(reader.pages[int(part)-1])
        else:
            for page in reader.pages:
                writer.add_page(page)

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(temp.name)

        with open(temp.name, "rb") as f:
            shared = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=profile.share_days())
            )
            shared.file.save("split.pdf", File(f))

        os.remove(temp.name)
        profile.increment()

        return render(request, "split.html", {
            "share_url": request.build_absolute_uri(
                f"/share/{shared.token}/"
            )
        })

    return render(request, "split.html")

@login_required
def compress(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES.get("files")

        reader = PdfReader(pdf)
        writer = PdfWriter()

        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(temp.name)

        with open(temp.name, "rb") as f:
            shared = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=profile.share_days())
            )
            shared.file.save("compressed.pdf", File(f))

        os.remove(temp.name)
        profile.increment()

        return render(request, "compress.html", {
            "share_url": request.build_absolute_uri(
                f"/share/{shared.token}/"
            )
        })

    return render(request, "compress.html")

# =====================================================
# SHARE
# =====================================================

def share_file(request, token):
    shared = get_object_or_404(SharedFile, token=token)

    if shared.is_expired():
        return render(request, "share_expired.html")

    if request.GET.get("download") == "1":
        return pdf_response(
            shared.file.path,
            os.path.basename(shared.file.name),
            inline=False
        )

    return render(request, "share_public.html", {
        "file": shared,
        "view_url": request.build_absolute_uri(),
        "download_url": request.build_absolute_uri() + "?download=1",
    })


# =====================================================
# CONVERSIONS
# =====================================================

@login_required
def pdf_to_word(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES["file"]

        reader = PdfReader(pdf)
        doc = Document()

        for page in reader.pages:
            text = page.extract_text()
            if text:
                doc.add_paragraph(text)

        # ✅ Create temp path WITHOUT keeping file open
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"{uuid.uuid4()}.docx"
        )

        # ✅ Save DOCX safely
        doc.save(temp_path)

        # ✅ Store in SharedFile
        with open(temp_path, "rb") as f:
            shared = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=profile.share_days())
            )
            shared.file.save(os.path.basename(temp_path), File(f))

        # ✅ Now delete (no lock anymore)
        os.remove(temp_path)

        profile.increment()

        share_url = request.build_absolute_uri(f"/share/{shared.token}/")
        return render(request, "share_link.html", {"share_url": share_url})

    return render(request, "pdf_to_word.html")



@login_required
def pdf_to_image(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES["file"]

        # ✅ Save uploaded PDF to temp path
        pdf_temp_path = os.path.join(
            tempfile.gettempdir(),
            f"{uuid.uuid4()}.pdf"
        )

        with open(pdf_temp_path, "wb") as f:
            for chunk in pdf.chunks():
                f.write(chunk)

        # ✅ Convert PDF → images
        images = convert_from_path(pdf_temp_path)

        # ✅ Create ZIP temp path (NO NamedTemporaryFile)
        zip_path = os.path.join(
            tempfile.gettempdir(),
            f"{uuid.uuid4()}.zip"
        )

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for i, img in enumerate(images):
                img_path = os.path.join(
                    tempfile.gettempdir(),
                    f"page_{i+1}.png"
                )
                img.save(img_path, "PNG")
                zipf.write(img_path, arcname=f"page_{i+1}.png")
                os.remove(img_path)

        # ✅ Save ZIP to SharedFile
        with open(zip_path, "rb") as f:
            shared = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=profile.share_days())
            )
            shared.file.save("images.zip", File(f))

        # ✅ Cleanup (no locks)
        os.remove(pdf_temp_path)
        os.remove(zip_path)

        profile.increment()

        return render(request, "share_link.html", {
            "share_url": request.build_absolute_uri(
                f"/share/{shared.token}/"
            )
        })

    return render(request, "pdf_to_image.html")
