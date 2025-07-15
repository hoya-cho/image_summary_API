FROM python:3.11-slim

# 1. 시스템 패키지 설치 (필요한 빌드 도구 및 런타임 라이브러리)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

# 2. yolov12 레포와 flash-attn wheel 파일을 복사 (호스트에 이미 존재한다고 가정)
COPY ./yolov12 /opt/yolov12
#COPY ./flash_attn-2.7.3+cu11torch2.2cxx11abiFALSE-cp311-cp311-linux_x86_64.whl /opt/

WORKDIR /opt/yolov12

# 3. requirements.txt 설치 (YOLOv12 공식 requirements)
RUN pip install --no-cache-dir -r requirements.txt

# 4. flash-attention 설치
#RUN pip install --no-cache-dir /opt/flash_attn-2.7.3+cu11torch2.2cxx11abiFALSE-cp311-cp311-linux_x86_64.whl

# 5. yolov12 소스 설치 (editable mode)
RUN pip install --no-cache-dir -e .

# 6. FastAPI 서버 코드 복사 (main.py, model_handler.py, yolov12n.pt, requirements_server.txt 등)
WORKDIR /app

COPY requirements_server.txt .
RUN pip install --no-cache-dir -r requirements_server.txt

COPY ./app /app/app


# 8. 환경변수 (YOLOv12 ultralytics fork를 PYTHONPATH에 추가)
ENV PYTHONPATH="${PYTHONPATH}:/opt/yolov12"

EXPOSE 8000

# 9. FastAPI 서버 실행 (main.py의 인스턴스 이름에 따라 조정)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 