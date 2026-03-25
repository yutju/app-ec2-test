# main.py
import os
import uuid
import shutil
import logging
import subprocess
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

# [복구된 기능] Prometheus & Rate Limiting 모듈
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from templates import HTML_CONTENT
from converter import process_conversion

# --- [1. 로그 및 환경 설정] ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SixSense-Converter")

app = FastAPI(title="SixSense Doc-Converter")

# --- [복구된 기능] Rate Limiter 설정 (IP당 1분 최대 5회) ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- [복구된 기능] Prometheus 메트릭 설정 ---
CONVERSION_REQUESTS = Counter(
    'doc_conversion_requests_total',
    'Total document conversion requests',
    ['status', 'file_type']
)
CONVERSION_DURATION = Histogram(
    'doc_conversion_duration_seconds',
    'Document conversion processing time',
    ['file_type']
)

# [개선된 기능] 컨테이너 내부 절대 경로로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp_storage")
os.makedirs(TEMP_DIR, exist_ok=True)

# --- [2. 로컬 파일 정리 함수] ---
def cleanup_local_files(*filepaths: str):
    for path in filepaths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Cleanup: Local file removed at {path}")
        except Exception as e:
            logger.error(f"Cleanup Error for {path}: {str(e)}")

# 1. 루트 경로
@app.get("/", response_class=HTMLResponse)
async def read_root():
    logger.info("Root page accessed")
    return HTML_CONTENT

# 2. 헬스 체크
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# --- [복구된 기능] Prometheus Metrics Endpoint ---
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# 3. 변환 경로 (Rate Limit 적용)
@app.post("/convert-to-pdf/")
@limiter.limit("10/minute")
async def convert_any_to_pdf(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # 파일 용량 제한 체크 (100MB)
    MAX_SIZE = 100 * 1024 * 1024
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    ext = file.filename.split(".")[-1].lower()

    if file_size > MAX_SIZE:
        CONVERSION_REQUESTS.labels(status='failed', file_type=ext).inc()
        logger.warning(f"File size limit exceeded: {file.filename} ({file_size} bytes)")
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다. 최대 100MB까지 가능합니다.")

    file_id = str(uuid.uuid4())

    # [개선된 기능] 입력/출력 경로를 모두 절대 경로로 확정
    input_path = os.path.join(TEMP_DIR, f"{file_id}.{ext}")
    output_path = os.path.join(TEMP_DIR, f"{file_id}.pdf")

    logger.info(f"Starting conversion: {file.filename} (ID: {file_id})")

    # [개선된 기능] 파일 저장 시 디스크 쓰기 완료 보장
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            buffer.flush()
            os.fsync(buffer.fileno()) # 물리적 저장 확인
    except Exception as e:
        logger.error(f"File save error: {str(e)}")
        raise HTTPException(status_code=500, detail="서버에 파일을 저장하지 못했습니다.")

    start_time = time.time() # 변환 시작 시간 측정

    try:
        # 변환 함수 호출 (절대 경로 전달)
        process_conversion(input_path, output_path, ext, TEMP_DIR)

        # 변환 결과 확인
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"PDF generation failed: {output_path} not found")

        # [복구된 기능] 성공 메트릭 기록 (소요 시간 및 성공 카운트)
        process_time = time.time() - start_time
        CONVERSION_DURATION.labels(file_type=ext).observe(process_time)
        CONVERSION_REQUESTS.labels(status='success', file_type=ext).inc()

        logger.info(f"Successfully converted: {file.filename} in {process_time:.2f}s")

        # [개선된 기능] 파일 응답 및 전송 후 삭제 로직
        # 1. 입력 원본 파일은 즉시 삭제 예약 (FastAPI BackgroundTasks)
        background_tasks.add_task(cleanup_local_files, input_path)

        # 2. 출력 PDF 파일은 클라이언트가 다운로드를 마친 후에 삭제 (FileResponse Background)
        response = FileResponse(
            output_path,
            media_type="application/pdf",
            filename=f"converted_{file.filename.rsplit('.', 1)[0]}.pdf"
        )
        response.background = BackgroundTasks()
        response.background.add_task(cleanup_local_files, output_path)

        return response

    except Exception as e:
        # [복구된 기능] 실패 메트릭 기록
        CONVERSION_REQUESTS.labels(status='failed', file_type=ext).inc()
        logger.error(f"Conversion failed for {file.filename}: {str(e)}")

        # 에러 발생 시 생성된 파일들 정리
        cleanup_local_files(input_path, output_path)

        status_code = 504 if isinstance(e, TimeoutError) else 500
        raise HTTPException(status_code=status_code, detail=f"변환 실패: {str(e)}")

