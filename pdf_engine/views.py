from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.utils import timezone
from datetime import timedelta
from django.core.mail import EmailMessage

from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from docx import Document
from pdf2image import convert_from_path
from docx2pdf import convert as docx2pdf_convert
from PIL import Image

import pandas as pd
import tabula
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pytesseract

import tempfile, os, zipfile, uuid

from openpyxl import load_workbook

from accounts.models import UserProfile
from .models import SharedFile

# =====================================================
# UTILITIES
# =====================================================
@login_required
def view_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    if shared.expire_at < timezone.now():
        messages.error(request, "Link expired")
        return redirect("my_documents")

    return FileResponse(
        shared.file.open("rb"),
        as_attachment=False,
        filename=os.path.basename(shared.file.name),
    )


@login_required
def download_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    return FileResponse(
        shared.file.open("rb"),
        as_attachment=True,
        filename=os.path.basename(shared.file.name),
    )


@login_required
def delete_pdf(request, token):
    shared = get_object_or_404(SharedFile, token=token, user=request.user)
    shared.file.delete()
    shared.delete()
    messages.success(request, "File deleted")
    return redirect("my_documents")

from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import render

from .models import SharedFile


@login_required
def dashboard(request):
    files = SharedFile.objects.filter(
        user=request.user
    ).order_by("-created_at")

    return render(request, "dashboard.html", {
        "files": files,
        "now": timezone.now(),
    })



def unlock_pdf(uploaded_file, password=None):
    """Unlock PDF and return temporary file path"""
    uploaded_file.seek(0)
    reader = PdfReader(uploaded_file)

    if reader.is_encrypted:
        if not password:
            raise ValueError("PDF is encrypted. Password required.")
        if not reader.decrypt(password):
            raise ValueError("Incorrect password.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
    with open(temp_path, "wb") as f:
        writer.write(f)

    return temp_path

def create_shared_file(user, file_path, filename, days):
    """Save file in SharedFile and return object"""
    with open(file_path, "rb") as f:
        shared = SharedFile.objects.create(
            user=user,
            expire_at=timezone.now() + timedelta(days=days)
        )
        shared.file.save(filename, File(f))
    return shared

def ensure_visible_sheet(xlsx_path):
    """Ensure Excel file has at least one visible sheet"""
    wb = load_workbook(xlsx_path)
    visible_found = any(s.sheet_state == "visible" for s in wb.worksheets)
    if not visible_found:
        wb.worksheets[0].sheet_state = "visible"
        wb.save(xlsx_path)

# =====================================================
# STATIC PAGES
# =====================================================

def tools(request):
    return render(request, "tools.html")

def pricing(request):
    return render(request, "pricing.html")

@login_required
def my_documents(request):
    files = SharedFile.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "my_documents.html", {"files": files})

# =====================================================
# SHARING FILES
# =====================================================

@login_required
def share_file(request, token):
    shared = get_object_or_404(SharedFile, token=token)
    if shared.expire_at < timezone.now():
        messages.error(request, "Link expired.")
        return redirect("tools")

    if request.method == "POST":
        email = request.POST.get("email")
        if email:
            EmailMessage(
                "Your file is ready",
                f"Download here:\n{request.build_absolute_uri()}",
                to=[email]
            ).send()
            messages.success(request, "Email sent.")
            return redirect("share_file", token=token)

    return FileResponse(
        shared.file.open("rb"),
        as_attachment=request.GET.get("download") == "1",
        filename=os.path.basename(shared.file.name)
    )

# =====================================================
# PDF TOOLS
# =====================================================

@login_required
def unlock_pdf_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES.get("file")
        password = request.POST.get("password")
        if not pdf:
            messages.error(request, "Upload a PDF.")
            return redirect("unlock_pdf_view")

        try:
            unlocked_path = unlock_pdf(pdf, password)
            shared = create_shared_file(
                request.user,
                unlocked_path,
                f"unlocked_{pdf.name}",
                profile.share_days()
            )
        except Exception as e:
            messages.error(request, str(e))
            return redirect("unlock_pdf_view")
        finally:
            if 'unlocked_path' in locals() and os.path.exists(unlocked_path):
                os.remove(unlocked_path)

        profile.increment()
        return render(request, "unlock.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "unlock.html")

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
        temp_paths = []
        try:
            for f in files:
                path = unlock_pdf(f)
                temp_paths.append(path)
                merger.append(path)
            out_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
            merger.write(out_path)
            merger.close()
            shared = create_shared_file(request.user, out_path, "merged.pdf", profile.share_days())
        finally:
            for p in temp_paths:
                if os.path.exists(p): os.remove(p)
            if os.path.exists(out_path): os.remove(out_path)

        profile.increment()
        return render(request, "merge.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "merge.html")

@login_required
def split(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        pdf = request.FILES.get("file")
        pages = request.POST.get("pages")
        if not pdf or not pages:
            messages.error(request, "PDF and pages required.")
            return redirect("split")

        path = unlock_pdf(pdf)
        reader = PdfReader(path)
        writer = PdfWriter()
        try:
            for part in pages.split(","):
                if "-" in part:
                    s, e = map(int, part.split("-"))
                    for i in range(s-1, e):
                        if i < len(reader.pages):
                            writer.add_page(reader.pages[i])
                else:
                    i = int(part)-1
                    if i < len(reader.pages):
                        writer.add_page(reader.pages[i])

            out = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
            with open(out, "wb") as f:
                writer.write(f)
            shared = create_shared_file(request.user, out, "split.pdf", profile.share_days())
        finally:
            os.remove(path)
            os.remove(out)

        profile.increment()
        return render(request, "split.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "split.html")

@login_required
def compress(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        pdf = request.FILES.get("file")
        path = unlock_pdf(pdf)
        reader = PdfReader(path)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        out = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
        with open(out, "wb") as f:
            writer.write(f)
        shared = create_shared_file(request.user, out, "compressed.pdf", profile.share_days())
        os.remove(path)
        os.remove(out)
        profile.increment()
        return render(request, "compress.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "compress.html")

# =====================================================
# CONVERSIONS
# =====================================================

@login_required
def pdf_to_word(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        pdf = request.FILES.get("file")
        path = unlock_pdf(pdf)
        doc = Document()
        reader = PdfReader(path)
        for p in reader.pages:
            text = p.extract_text()
            if text:
                doc.add_paragraph(text)

        out = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.docx")
        doc.save(out)
        shared = create_shared_file(request.user, out, "output.docx", profile.share_days())
        os.remove(path)
        os.remove(out)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "pdf_to_word.html")

@login_required
def pdf_to_image(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        pdf = request.FILES.get("file")
        path = unlock_pdf(pdf)
        images = convert_from_path(path, dpi=200, poppler_path=r"C:\poppler\Library\bin")
        zip_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.zip")
        with zipfile.ZipFile(zip_path, "w") as z:
            for i, img in enumerate(images, 1):
                img_path = os.path.join(tempfile.gettempdir(), f"page_{i}.png")
                img.save(img_path)
                z.write(img_path, f"page_{i}.png")
                os.remove(img_path)

        shared = create_shared_file(request.user, zip_path, "images.zip", profile.share_days())
        os.remove(path)
        os.remove(zip_path)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "pdf_to_image.html")

@login_required
def word_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        docx = request.FILES.get("file")
        docx_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.docx")
        with open(docx_path, "wb") as f:
            for c in docx.chunks(): f.write(c)
        pdf_path = docx_path.replace(".docx", ".pdf")
        docx2pdf_convert(docx_path, pdf_path)
        shared = create_shared_file(request.user, pdf_path, "output.pdf", profile.share_days())
        os.remove(docx_path)
        os.remove(pdf_path)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})
    return render(request, "word_to_pdf.html")

@login_required
def image_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        images = request.FILES.getlist("file")
        img_objs = []
        for img in images:
            im = Image.open(img)
            if im.mode != "RGB": im = im.convert("RGB")
            img_objs.append(im)
        pdf_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.pdf")
        img_objs[0].save(pdf_path, save_all=True, append_images=img_objs[1:])
        shared = create_shared_file(request.user, pdf_path, "images.pdf", profile.share_days())
        os.remove(pdf_path)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})
    return render(request, "image_to_pdf.html")

# =====================================================
# PDF TO EXCEL WITH OCR FALLBACK
# =====================================================

@login_required
def pdf_to_excel(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        pdf = request.FILES.get("file")
        password = request.POST.get("password")
        if not pdf:
            messages.error(request, "Please upload a PDF file.")
            return redirect("pdf_to_excel")

        try:
            pdf_path = unlock_pdf(pdf, password)
        except Exception as e:
            messages.error(request, str(e))
            return redirect("pdf_to_excel")

        excel_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.xlsx")

        try:
            # Try table extraction
            tables = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True, lattice=True, stream=True)

            # Fallback to PyPDF2 text extraction
            if not tables or all(t.empty for t in tables):
                reader = PdfReader(pdf_path)
                rows = []
                for p in reader.pages:
                    text = p.extract_text()
                    if text:
                        for line in text.splitlines():
                            if line.strip(): rows.append([line])
                # Fallback to OCR if still empty
                if not rows:
                    images = convert_from_path(pdf_path, dpi=300)
                    for img in images:
                        text = pytesseract.image_to_string(img)
                        for line in text.splitlines():
                            if line.strip(): rows.append([line])
                if not rows: raise ValueError("PDF has no tables or extractable text.")
                tables = [pd.DataFrame(rows, columns=["Content"])]

            # Write Excel
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                for i, table in enumerate(tables):
                    table.to_excel(writer, sheet_name=f"Sheet_{i+1}", index=False)
            ensure_visible_sheet(excel_path)

        except Exception as e:
            os.remove(pdf_path)
            messages.error(request, f"Conversion failed: {e}")
            return redirect("pdf_to_excel")

        shared = create_shared_file(request.user, excel_path, "output.xlsx", profile.share_days())
        os.remove(pdf_path)
        os.remove(excel_path)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "pdf_to_excel.html")

# =====================================================
# EXCEL TO PDF
# =====================================================

@login_required
def excel_to_pdf(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.can_use():
        messages.error(request, "Daily limit reached.")
        return redirect("tools")

    if request.method == "POST":
        excel = request.FILES.get("file")
        if not excel or not excel.name.lower().endswith((".xls", ".xlsx")):
            messages.error(request, "Please upload an Excel file.")
            return redirect("excel_to_pdf")

        excel_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.xlsx")
        with open(excel_path, "wb") as f:
            for chunk in excel.chunks(): f.write(chunk)

        df = pd.read_excel(excel_path)
        pdf_path = excel_path.replace(".xlsx", ".pdf")

        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        x, y = 40, height - 40
        for col in df.columns:
            c.drawString(x, y, str(col))
            x += 120
        y -= 20
        for _, row in df.iterrows():
            x = 40
            for val in row:
                c.drawString(x, y, str(val))
                x += 120
            y -= 20
            if y < 40:
                c.showPage()
                y = height - 40
        c.save()

        shared = create_shared_file(request.user, pdf_path, "output.pdf", profile.share_days())
        os.remove(excel_path)
        os.remove(pdf_path)
        profile.increment()
        return render(request, "share_link.html", {"share_url": request.build_absolute_uri(f"/share/{shared.token}/")})

    return render(request, "excel_to_pdf.html")
