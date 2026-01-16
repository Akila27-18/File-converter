import os
import uuid
import tempfile
import zipfile
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.files import File

from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from docx import Document
from docx2pdf import convert as docx2pdf_convert
from pdf2image import convert_from_path
from PIL import Image
from .forms import SplitPDFForm, MergePDFForm, CompressPDFForm

import pandas as pd
import tabula
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from openpyxl import load_workbook

from .models import SharedFile
from accounts.models import UserProfile

# =====================================================
# UTILITIES
# =====================================================

def unlock_pdf(uploaded_file, password=None):
    if not uploaded_file:
        raise ValueError("No PDF uploaded")

    uploaded_file.seek(0)
    reader = PdfReader(uploaded_file)

    if reader.is_encrypted:
        if not password or not reader.decrypt(password):
            raise ValueError("Invalid PDF password")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
    with open(path, "wb") as f:
        writer.write(f)

    return path


def create_shared_file(user, file_path, filename, days):
    with open(file_path, "rb") as f:
        shared = SharedFile.objects.create(
            user=user,
            expire_at=timezone.now() + timedelta(days=days)
        )
        shared.file.save(filename, File(f))
    return shared


def ensure_visible_sheet(xlsx_path):
    wb = load_workbook(xlsx_path)
    if not any(ws.sheet_state == "visible" for ws in wb.worksheets):
        wb.worksheets[0].sheet_state = "visible"
        wb.save(xlsx_path)
# =====================================================
# STATIC / DASHBOARD
# =====================================================

def tools(request):
    return render(request, "tools.html")


def pricing(request):
    return render(request, "pricing.html")


@login_required
def dashboard(request):
    files = SharedFile.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "dashboard.html", {"files": files})


@login_required
def my_documents(request):
    files = SharedFile.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "my_documents.html", {"files": files})
# =====================================================
# VIEW / DOWNLOAD / DELETE / SHARE
# =====================================================

@login_required
def view_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    if shared.expire_at and shared.expire_at < timezone.now():
        messages.error(request, "Link expired")
        return redirect("my_documents")
    return FileResponse(shared.file.open("rb"), as_attachment=False)


@login_required
def download_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    return FileResponse(shared.file.open("rb"), as_attachment=True)


@login_required
def delete_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token, user=request.user)
    shared.file.delete(save=False)
    shared.delete()
    messages.success(request, "File deleted")
    return redirect("my_documents")


@login_required
def share_file(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    return FileResponse(
        shared.file.open("rb"),
        as_attachment=request.GET.get("download") == "1"
    )
# =====================================================
# PDF TOOLS
# =====================================================

@login_required
def unlock_pdf_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        pdf = request.FILES.get("file")
        password = request.POST.get("password")

        try:
            path = unlock_pdf(pdf, password)
            shared = create_shared_file(
                request.user, path, f"unlocked_{pdf.name}", profile.share_days()
            )
        except Exception as e:
            messages.error(request, str(e))
            return redirect("unlock_pdf")
        finally:
            if "path" in locals() and os.path.exists(path):
                os.remove(path)

        profile.increment()
        return render(request, "unlock.html", {
            "share_url": f"/share/{shared.token}/"
        })

    return render(request, "unlock.html")

import os
import uuid
import tempfile
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.files import File

from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from .models import SharedFile
from accounts.models import UserProfile

# =================== Utilities ===================

def unlock_pdf(uploaded_file, password=None):
    """Unlocks an uploaded PDF and saves a temp copy."""
    if not uploaded_file:
        raise ValueError("No PDF uploaded")

    uploaded_file.seek(0)
    reader = PdfReader(uploaded_file)

    if reader.is_encrypted:
        if not password or not reader.decrypt(password):
            raise ValueError("Invalid PDF password")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
    with open(temp_path, "wb") as f:
        writer.write(f)

    return temp_path

def create_shared_file(user, file_path, filename, days):
    """Create a SharedFile entry for download or sharing."""
    with open(file_path, "rb") as f:
        shared = SharedFile.objects.create(
            user=user,
            expire_at=timezone.now() + timedelta(days=days)
        )
        shared.file.save(filename, File(f))
    return shared

# =================== Merge PDF ===================

@login_required
def merge(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        files = request.FILES.getlist("pdf_files")  # matches your form field
        if len(files) < 2:
            messages.error(request, "Select at least 2 PDFs")
            return redirect("merge")

        merger = PdfMerger()
        temp_paths = []

        try:
            for f in files:
                temp_path = unlock_pdf(f)
                temp_paths.append(temp_path)
                with open(temp_path, "rb") as pdf_file:
                    merger.append(pdf_file)

            output_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
            merger.write(output_path)
            merger.close()

            shared = create_shared_file(
                request.user, output_path, "merged.pdf", profile.share_days()
            )

        finally:
            # Clean up temp files safely
            for path in temp_paths + [output_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except PermissionError:
                    pass

        profile.increment()
        return render(request, "merge.html", {"share_url": f"/share/{shared.token}/"})

    return render(request, "merge.html")




# ================= SPLIT =================
@login_required
def split_pdf_view(request):
    if request.method == 'POST':
        form = SplitPDFForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            split_mode = form.cleaned_data['split_mode']
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
            writers = []

            # Fixed split
            if split_mode == 'fixed':
                range_size = form.cleaned_data['range_size']
                for i in range(0, num_pages, range_size):
                    writer = PdfWriter()
                    for j in range(i, min(i + range_size, num_pages)):
                        writer.add_page(reader.pages[j])
                    writers.append(writer)

            # Custom ranges
            else:
                custom_ranges = form.cleaned_data['custom_ranges']
                try:
                    for part in custom_ranges.split(','):
                        writer = PdfWriter()
                        if '-' in part:
                            start, end = map(int, part.split('-'))
                            for i in range(start - 1, min(end, num_pages)):
                                writer.add_page(reader.pages[i])
                        else:
                            i = int(part) - 1
                            if i < num_pages:
                                writer.add_page(reader.pages[i])
                        writers.append(writer)
                except Exception:
                    form.add_error('custom_ranges', 'Invalid page range format.')
                    return render(request, 'split_pdf.html', {'form': form})

            # Save temp PDFs
            temp_paths = []
            for idx, writer in enumerate(writers, start=1):
                path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_part{idx}.pdf")
                with open(path, 'wb') as f:
                    writer.write(f)
                temp_paths.append(path)

            message = f"{len(temp_paths)} PDF(s) created."
            return render(request, 'split_pdf.html', {'form': form, 'message': message, 'files': temp_paths})

    else:
        form = SplitPDFForm()

    return render(request, 'split.html', {'form': form})


# ================= COMPRESS =================
@login_required
def compress(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = CompressPDFForm(request.POST, request.FILES)
        if form.is_valid():
            pdf = request.FILES['pdf_file']
            path = unlock_pdf(pdf)
            reader = PdfReader(path)
            writer = PdfWriter()

            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)

            compressed_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
            with open(compressed_path, "wb") as f:
                writer.write(f)

            shared = create_shared_file(
                request.user, compressed_path, "compressed.pdf", profile.share_days()
            )

            # Cleanup temp
            try: os.remove(path)
            except PermissionError: pass
            try: os.remove(compressed_path)
            except PermissionError: pass

            profile.increment()
            return render(request, "compress.html", {"form": form, "share_url": f"/share/{shared.token}/"})
    else:
        form = CompressPDFForm()

    return render(request, "compress.html", {"form": form})

# =====================================================
# CONVERSIONS
# =====================================================

@login_required
def word_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        file = request.FILES.get("file")

        docx_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.docx")
        pdf_path = docx_path.replace(".docx", ".pdf")

        with open(docx_path, "wb") as f:
            for c in file.chunks():
                f.write(c)

        docx2pdf_convert(docx_path, pdf_path)

        shared = create_shared_file(
            request.user, pdf_path, "output.pdf", profile.share_days()
        )

        os.remove(docx_path)
        os.remove(pdf_path)
        profile.increment()

        return render(request, "word_to_pdf.html", {
            "share_url": f"/share/{shared.token}/"
        })

    return render(request, "word_to_pdf.html")

@login_required
def image_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        images = request.FILES.getlist("files")
        pil = []

        for img in images:
            im = Image.open(img)
            if im.mode != "RGB":
                im = im.convert("RGB")
            pil.append(im)

        pdf_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
        pil[0].save(pdf_path, save_all=True, append_images=pil[1:])

        shared = create_shared_file(
            request.user, pdf_path, "images.pdf", profile.share_days()
        )

        os.remove(pdf_path)
        profile.increment()

        return render(request, "image_to_pdf.html", {
            "share_url": f"/share/{shared.token}/"
        })

    return render(request, "image_to_pdf.html")

@login_required
def pdf_to_excel(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        pdf = request.FILES.get("file")
        path = unlock_pdf(pdf)

        excel = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.xlsx")

        tables = tabula.read_pdf(path, pages="all", multiple_tables=True)

        if not tables:
            reader = PdfReader(path)
            rows = []
            for p in reader.pages:
                text = p.extract_text()
                if text:
                    for line in text.splitlines():
                        rows.append([line])
            tables = [pd.DataFrame(rows, columns=["Content"])]

        with pd.ExcelWriter(excel, engine="openpyxl") as writer:
            for i, t in enumerate(tables):
                t.to_excel(writer, sheet_name=f"Sheet{i+1}", index=False)

        ensure_visible_sheet(excel)

        shared = create_shared_file(
            request.user, excel, "output.xlsx", profile.share_days()
        )

        os.remove(path)
        os.remove(excel)
        profile.increment()

        return render(request, "pdf_to_excel.html", {
            "share_url": f"/share/{shared.token}/"
        })

    return render(request, "pdf_to_excel.html")

@login_required
def excel_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        excel = request.FILES.get("file")

        excel_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.xlsx")
        with open(excel_path, "wb") as f:
            for c in excel.chunks():
                f.write(c)

        df = pd.read_excel(excel_path)
        pdf_path = excel_path.replace(".xlsx", ".pdf")

        c = canvas.Canvas(pdf_path, pagesize=A4)
        w, h = A4
        y = h - 40

        for _, row in df.iterrows():
            x = 40
            for v in row:
                c.drawString(x, y, str(v))
                x += 120
            y -= 20
            if y < 40:
                c.showPage()
                y = h - 40

        c.save()

        shared = create_shared_file(
            request.user, pdf_path, "output.pdf", profile.share_days()
        )

        os.remove(excel_path)
        os.remove(pdf_path)
        profile.increment()

        return render(request, "excel_to_pdf.html", {
            "share_url": f"/share/{shared.token}/"
        })
    return render(request, "excel_to_pdf.html")

@login_required
def pdf_to_word(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        pdf = request.FILES.get("file")

        if not pdf:
            messages.error(request, "Please upload a PDF file.")
            return redirect("pdf_to_word")

        try:
            pdf_path = unlock_pdf(pdf)
            reader = PdfReader(pdf_path)
            doc = Document()

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    doc.add_paragraph(text)

            docx_path = os.path.join(
                tempfile.gettempdir(), f"{uuid.uuid4()}.docx"
            )
            doc.save(docx_path)

            shared = create_shared_file(
                request.user,
                docx_path,
                "output.docx",
                profile.share_days()
            )

        except Exception as e:
            messages.error(request, f"Conversion failed: {e}")
            return redirect("pdf_to_word")

        finally:
            if "pdf_path" in locals() and os.path.exists(pdf_path):
                os.remove(pdf_path)
            if "docx_path" in locals() and os.path.exists(docx_path):
                os.remove(docx_path)

        profile.increment()
        return render(
            request,
            "pdf_to_word.html",
            {"share_url": f"/share/{shared.token}/"}
        )

    return render(request, "pdf_to_word.html")
@login_required
def pdf_to_image(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        pdf = request.FILES.get("file")

        if not pdf:
            messages.error(request, "Please upload a PDF file.")
            return redirect("pdf_to_image")

        try:
            # Unlock PDF (handles encrypted + normal PDFs)
            pdf_path = unlock_pdf(pdf)

            # Convert PDF → images
            images = convert_from_path(
                pdf_path,
                dpi=200,
                poppler_path=r"C:\poppler\Library\bin"  # ⚠️ REQUIRED ON WINDOWS
            )

            # Zip output
            zip_path = os.path.join(
                tempfile.gettempdir(), f"{uuid.uuid4()}.zip"
            )

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for i, img in enumerate(images, start=1):
                    img_path = os.path.join(
                        tempfile.gettempdir(), f"page_{i}.png"
                    )
                    img.save(img_path, "PNG")
                    z.write(img_path, f"page_{i}.png")
                    os.remove(img_path)

            shared = create_shared_file(
                request.user,
                zip_path,
                "images.zip",
                profile.share_days()
            )

        except Exception as e:
            messages.error(request, f"Conversion failed: {e}")
            return redirect("pdf_to_image")

        finally:
            if "pdf_path" in locals() and os.path.exists(pdf_path):
                os.remove(pdf_path)
            if "zip_path" in locals() and os.path.exists(zip_path):
                os.remove(zip_path)

        profile.increment()
        return render(
            request,
            "pdf_to_image.html",
            {"share_url": f"/share/{shared.token}/"}
        )

    return render(request, "pdf_to_image.html")

