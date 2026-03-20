# 1단계: 베이스 이미지 (가장 안정적인 Python 3.10-slim)
FROM python:3.10-slim

# 2단계: 환경 변수 (인터랙티브 모드 방지 및 한글 설정)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=ko_KR.UTF-8

# 3단계: 시스템 패키지 (한글 폰트 설치 필수)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-nanum \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 4단계: 컨테이너 실행 유저 (k3s 권장 보안 설정)
RUN useradd -m -u 1000 appuser

# 5단계: 라이브러리 설치 (가장 확실하게 설치되는 패키지들)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6단계: 소스 복사 및 권한 설정 보강
COPY . .
# [핵심] temp_storage 생성 및 appuser에게 소유권 부여 (k3s 볼륨 마운트 대비)
RUN mkdir -p /app/temp_storage && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/temp_storage

USER appuser

# 7단계: 컨테이너 실행 (비루트 실행)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
