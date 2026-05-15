# 单镜像：FastAPI（本机 8000）+ Nginx 静态前端 + /api 反代
# 构建：docker build -f docker/Dockerfile -t mistake-notebook:local --build-arg APP_VERSION=1.0.0 --build-arg VITE_APP_VERSION=1.0.0 .

# === 阶段 1：前端静态资源 ===
FROM node:22-alpine AS web-build
WORKDIR /web

ARG VITE_APP_VERSION=dev
ENV VITE_APP_VERSION=${VITE_APP_VERSION}

COPY frontend/package.json /web/package.json
RUN npm install
COPY frontend /web
RUN npm run build

# === 阶段 2：运行时 ===
FROM python:3.12-slim

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends nginx tini \
  && rm -rf /var/lib/apt/lists/* \
  && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /web/dist /usr/share/nginx/html

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/api/health', timeout=4)" || exit 1

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/entrypoint.sh"]
