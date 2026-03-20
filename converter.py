# converter.py
import os
import logging
import olefile
from docx import Document  # pip install python-docx
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger("SixSense-Converter")

def process_conversion(input_path, output_path, ext, temp_dir):
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    pdfmetrics.registerFont(TTFont("NanumGothic", font_path))

    # [1] 이미지 변환 (기존 동일)
    if ext in ["png", "jpg", "jpeg", "bmp"]:
        with Image.open(input_path) as img:
            if img.mode != "RGB": img = img.convert("RGB")
            img.save(output_path, "PDF")
        return

    # [2] 문서 변환 (TXT, HWP, DOCX 통합)
    elif ext in ["txt", "hwp", "docx"]:
        try:
            c = canvas.Canvas(output_path)
            c.setFont("NanumGothic", 10)
            y_position = 800
            lines = []

            # 2-1. DOCX 처리 (워드)
            if ext == "docx":
                doc = Document(input_path)
                for para in doc.paragraphs:
                    lines.append(para.text)

            # 2-2. HWP 처리 (한글)
            elif ext == "hwp":
                with olefile.OleFileIO(input_path) as ole:
                    if ole.exists('PrvText'):
                        data = ole.openstream('PrvText').read()
                        lines = data.decode('utf-16').split('\n')

            # 2-3. TXT 처리
            elif ext == "txt":
                for enc in ['utf-8', 'cp949']:
                    try:
                        with open(input_path, 'r', encoding=enc) as f:
                            lines = f.readlines()
                        break
                    except: continue

            # PDF 그리기 (공통)
            for line in lines:
                if line.strip():
                    c.drawString(50, y_position, line.strip())
                    y_position -= 15
                    if y_position < 50:
                        c.showPage()
                        c.setFont("NanumGothic", 10)
                        y_position = 800
            c.save()
            logger.info(f"Successfully converted {ext.upper()}")

        except Exception as e:
            logger.error(f"{ext.upper()} Conversion Error: {str(e)}")
            raise e
