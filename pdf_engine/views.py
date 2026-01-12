from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.utils import timezone
from datetime import timedelta
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import tempfile, os

from accounts.models import UserProfile
from .models import SharedFile


# ---------------- Utilities ---------------- #

def pdf_response(path, filename, inline=False):
    """Return a PDF as attachment or inline for viewing."""
    with open(path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/pdf")
        disposition = "inline" if inline else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return response


def parse_pages(pages_str):
    """Parse page ranges like '1-3,5,7-9' -> [0,1,2,4,6,7,8]"""
    pages = set()
    for part in pages_str.split(","):
        if "-" in part:
            start, end = part.split("-")
            pages.update(range(int(start)-1, int(end)))
        else:
            pages.add(int(part)-1)
    return sorted(pages)


# ---------------- Views ---------------- #

def tools(request):
    """Landing page for PDF tools"""
    return render(request, "tools.html")


@login_required
def merge(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached. Upgrade to Pro.")
        return redirect("tools")

    if request.method == "POST":
        merger = PdfMerger()
        for file in request.FILES.getlist("files"):
            merger.append(file)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        merger.write(temp_file.name)
        merger.close()

        # Save using Django's FileField
        with open(temp_file.name, "rb") as f:
            django_file = File(f)
            shared_file = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=1)
            )
            shared_file.file.save(os.path.basename(temp_file.name), django_file)

        profile.increment()
        share_url = request.build_absolute_uri(f"/share/{shared_file.token}/")
        return render(request, "share_link.html", {"share_url": share_url})

    return render(request, "merge.html")


@login_required
def split(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf_file = request.FILES["file"]
        mode = request.POST.get("mode", "all")
        pages_input = request.POST.get("pages", "")

        reader = PdfReader(pdf_file)
        writer = PdfWriter()

        if mode == "all":
            for page in reader.pages:
                writer.add_page(page)
        else:
            for p in parse_pages(pages_input):
                if 0 <= p < len(reader.pages):
                    writer.add_page(reader.pages[p])

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(temp_file.name)

        # Save using Django's FileField
        with open(temp_file.name, "rb") as f:
            django_file = File(f)
            shared_file = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=1)
            )
            shared_file.file.save(os.path.basename(temp_file.name), django_file)

        profile.increment()
        share_url = request.build_absolute_uri(f"/share/{shared_file.token}/")
        return render(request, "share_link.html", {"share_url": share_url})

    return render(request, "split.html")


@login_required
def compress(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        reader = PdfReader(request.FILES["file"])
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(temp_file.name)

        # Save using Django's FileField
        with open(temp_file.name, "rb") as f:
            django_file = File(f)
            shared_file = SharedFile.objects.create(
                user=request.user,
                expire_at=timezone.now() + timedelta(days=1)
            )
            shared_file.file.save(os.path.basename(temp_file.name), django_file)

        profile.increment()
        share_url = request.build_absolute_uri(f"/share/{shared_file.token}/")
        return render(request, "share_link.html", {"share_url": share_url})

    return render(request, "compress.html")


# ---------------- Share ---------------- #

def share_file(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    if shared.is_expired():
        messages.error(request, "This link has expired.")
        return redirect("tools")
    return pdf_response(shared.file.path, os.path.basename(shared.file.name), inline=True)


@login_required
def my_documents(request):
    """Show all PDFs processed by the logged-in user"""
    files = SharedFile.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "my_documents.html", {"files": files, "now": timezone.now()})


def pricing(request):
    """Display pricing plans"""
    return render(request, "pricing.html")
