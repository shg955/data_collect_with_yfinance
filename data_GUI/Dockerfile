# Python 3.12.3 이미지를 기반으로 빌드
FROM python:3.12.3-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY requirements.txt /app/requirements.txt

# 의존성 설치
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . /app

# Streamlit 실행 포트 설정
EXPOSE 8501

# 기본 실행 명령어 설정
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]