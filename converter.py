# converter.py
import os
import logging
import olefile
from docx import Document  # pip install python-docx
from PIL import Image

# [핵심 수정] 수동 좌표(y_position) 계산 대신, 자동 줄바꿈을 지원하는 platypus 사용
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

logger = logging.getLogger("SixSense-Converter")

def process_conversion(input_path, output_path, ext, temp_dir):
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

    # 폰트가 없을 경우 에러 방지
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"폰트 파일을 찾을 수 없습니다: {font_path}")

    pdfmetrics.registerFont(TTFont("NanumGothic", font_path))

    # [1] 이미지 변환
    if ext in ["png", "jpg", "jpeg", "bmp"]:
        with Image.open(input_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output_path, "PDF")
        return

    # [2] 문서 변환 (TXT, HWP, DOCX 통합)
    elif ext in ["txt", "hwp", "docx"]:
        try:
            lines = []

            # 2-1. DOCX 처리 (텍스트만 추출)
            if ext == "docx":
                doc = Document(input_path)
                for para in doc.paragraphs:
                    if para.text.strip():
                        lines.append(para.text.strip())

            # 2-2. HWP 처리 (PrvText 텍스트만 추출)
            elif ext == "hwp":
                with olefile.OleFileIO(input_path) as ole:
                    if ole.exists('PrvText'):
                        # HWP 미리보기 텍스트는 보통 utf-16le로 인코딩되어 있습니다.
                        data = ole.openstream('PrvText').read()
                        try:
                            text_data = data.decode('utf-16le')
                        except UnicodeDecodeError:
                            text_data = data.decode('utf-16')
                        lines = text_data.split('\n')
                    else:
                        raise ValueError("HWP 파일 내에 추출할 수 있는 텍스트(PrvText)가 없습니다.")

            # 2-3. TXT 처리
            elif ext == "txt":
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        with open(input_path, 'r', encoding=enc) as f:
                            lines = f.readlines()
                        break
                    except UnicodeDecodeError:
                        continue

            # --- [핵심 수정: PDF 자동 줄바꿈 및 여백 자동 생성 로직] ---
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()

            # 커스텀 폰트 스타일 지정 (한글 깨짐 방지 및 아시아권 줄바꿈 지원)
            custom_style = ParagraphStyle(
                name='NanumStyle',
                fontName='NanumGothic',
                fontSize=10,
                leading=16,          # 줄 간격
                wordWrap='CJK'       # 한글/한자/일어 등에서 자연스러운 줄바꿈 처리
            )

            story = [] # PDF에 들어갈 내용물(문단들)을 담는 리스트

            for line in lines:
                clean_line = line.strip()
                if clean_line:
                    # Paragraph 객체를 쓰면 글자가 길어도 알아서 다음 줄로 넘어가고, 페이지도 알아서 넘깁니다.
                    story.append(Paragraph(clean_line, custom_style))
                    story.append(Spacer(1, 6)) # 문단 사이의 간격(여백) 추가

            # PDF 문서 조립
            doc.build(story)
            logger.info(f"Successfully converted {ext.upper()} (Text-only mode)")

        except Exception as e:
            logger.error(f"{ext.upper()} Conversion Error: {str(e)}")
            raise RuntimeError(f"문서 변환 중 오류 발생: {str(e)}")

    else:
        raise ValueError(f"지원하지 않는 형식입니다: {ext}")

