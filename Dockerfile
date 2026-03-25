# 1단계: 베이스 이미지 (안정적인 Python 3.10-slim)
FROM python:3.10-slim

# 2단계: 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=ko_KR.UTF-8
# K3s 파드 및 EC2 컨테이너 내부 로그 시간대를 한국 시간으로 맞추기 위해 필수
ENV TZ=Asia/Seoul

# 3단계: 시스템 패키지 설치
# LibreOffice(문서 변환 엔진)와 한글 폰트 설치를 포함합니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-java-common \
    default-jre \
    fonts-nanum \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4단계: 비루트(Non-root) 전용 그룹 및 유저 생성
RUN groupadd -r appgroup && useradd -r -g appgroup -m -u 1000 appuser

WORKDIR /app

# 5단계: 파이썬 패키지 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6단계: 소스 복사 및 권한 설정
# COPY 시점에 소유권을 appuser로 지정하여 레이어 용량을 최적화합니다.
COPY --chown=appuser:appgroup . .

# [핵심 수정] 권한 설정 로직 통합 🎖️
# 1. temp_storage 폴더 생성
# 2. app.log 빈 파일 생성 (Permission Denied 방지)
# 3. 모든 작업 파일에 대해 appuser에게 소유권 부여
RUN mkdir -p /app/temp_storage && \
    touch /app/app.log && \
    chown -R appuser:appgroup /app/temp_storage /app/app.log && \
    chmod 755 /app/temp_storage && \
    chmod 664 /app/app.log

# 7단계: 컨테이너 실행 유저 전환 (보안 강화)
# 이제부터 실행되는 모든 프로세스는 일반 사용자(appuser) 권한입니다.
USER appuser

# 8단계: 애플리케이션 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
