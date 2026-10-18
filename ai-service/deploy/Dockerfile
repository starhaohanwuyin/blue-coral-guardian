FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# OpenCV / Pillow 运行库
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# 权重与数据通过 docker-compose 挂载，不打进镜像
COPY scripts ./scripts
COPY web ./web

WORKDIR /app/scripts
EXPOSE 8000

CMD ["python", "serve_fusion.py", "--host", "0.0.0.0", "--port", "8000"]
