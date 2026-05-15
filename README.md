# AI 错题本

Vue 3 + Naive UI 前端，FastAPI + SQLite 后端。支持拍照/上传识图、流式 AI 分析、错题管理、统计图表、举一反三练习、科目与年级管理，以及可配置多家 OpenAI 兼容 AI。

## 功能概览

- **登录与权限**：JWT；首次启动自动创建管理员 `admin` / `123456`；管理员可创建子账号；错题数据按用户隔离。
- **错题录入**：上传题目图片并框选区域；**流式识图**生成题干与解析；支持 **重新识别** 并填写补充说明纠偏；题干支持 `<u>` 下划线与简单 Markdown 排版预览。
- **错题管理**：列表筛选、详情、编辑、更换配图；图片经鉴权接口访问。
- **举一反三**：基于原题生成练习题并 AI 批改。
- **统计**：按年级、科目、知识点标签分布（ECharts）；知识点图支持按年级/科目筛选。
- **年级 / 科目**：内置年级与科目维护。
- **AI 设置**：多厂商 OpenAI 兼容接入；可分别配置默认、识图、解题模型。
- **版本展示**：顶栏与移动端侧栏显示当前版本（来自构建注入或 `/api/version`）。

## 本地开发

### 后端

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

可选环境变量（`.env` 或系统环境）：

| 变量 | 说明 |
|------|------|
| `APP_SECRET` | 加密存储 API Key 的密钥，**生产环境务必修改** |
| `APP_VERSION` | 应用版本号，默认 `dev` |
| `DATABASE_URL` | 默认 `sqlite+aiosqlite:///./data/app.db` |
| `UPLOAD_DIR` | 上传图片目录，默认 `./data/uploads` |
| `CORS_ORIGINS` | 逗号分隔的跨域来源白名单；**不设置或留空则不限制**；需要收紧时再填写 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT 有效期（分钟），默认 7 天 |

公开接口（无需登录）：`GET /api/health`、`GET /api/version`、`POST /api/auth/login`。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`，Vite 将 `/api` 代理到后端 `8000`。

生产构建：

```powershell
npm run build
```

产物在 `frontend/dist`。部署时可将 `VITE_API_BASE` 留空，由 Nginx 同域反代 `/api`；版本号可通过构建参数 `VITE_APP_VERSION` 注入。

## Docker 部署

单容器镜像内同时包含 **FastAPI（监听本机 8000）** 与 **Nginx（对外 80）**：静态前端由 Nginx 托管，`/api/` 反代至本机后端。对外只需映射 **一个端口**（默认 `8080:80`）。

### `docker-compose.yml` 示例

仓库根目录已包含 `docker-compose.yml`，内容如下（**从源码构建**）：

```yaml
services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
      args:
        APP_VERSION: ${APP_VERSION:-dev}
        VITE_APP_VERSION: ${APP_VERSION:-dev}
    ports:
      - "8080:80"
    environment:
      APP_SECRET: ${APP_SECRET:-please-change-app-secret}
      APP_VERSION: ${APP_VERSION:-dev}
      DATABASE_URL: sqlite+aiosqlite:////data/app.db
      UPLOAD_DIR: /data/uploads
      # CORS_ORIGINS: 可选，逗号分隔白名单；不设置则不限制跨域
    volumes:
      - mistake_data:/data

volumes:
  mistake_data:
```

使用 **GHCR 预构建镜像** 时，可将 `build` 改为 `image`（将 `<owner>/<repo>` 换成你的 GitHub 仓库路径全小写，与 GHCR 包名一致）：

```yaml
services:
  app:
    image: ghcr.io/<owner>/mistake-notebook:v1.0.0
    ports:
      - "8080:80"
    environment:
      APP_SECRET: ${APP_SECRET:-please-change-app-secret}
      APP_VERSION: "1.0.0"
      DATABASE_URL: sqlite+aiosqlite:////data/app.db
      UPLOAD_DIR: /data/uploads
      # CORS_ORIGINS: http://192.168.1.10:8080  # 可选，限制跨域来源
    volumes:
      - mistake_data:/data

volumes:
  mistake_data:
```

也可直接使用仓库中的 `docker-compose.ghcr.yml`（通过环境变量指定镜像坐标与标签）。

也可在项目根目录创建 `.env` 供 Compose 读取（勿提交到 Git）：

```env
APP_SECRET=请替换为足够长的随机字符串
APP_VERSION=1.0.0
```

### 启动

在项目根目录：

```powershell
# 可选：指定版本号（会写入 API 与前端展示）
$env:APP_SECRET = "your-long-random-secret"
$env:APP_VERSION = "1.0.0"
docker compose up -d --build
```

使用预构建镜像且 compose 中已写 `image:` 时，可省略 `--build`：

```powershell
docker compose pull
docker compose up -d
```

- **应用**：`http://localhost:8080`（Nginx 托管静态页；浏览器通过同域 `/api/` 访问后端，容器内反代至本机 `127.0.0.1:8000`）

数据与上传文件保存在卷 `mistake_data`（容器内 `/data`）。首次部署请设置 `APP_SECRET`。

默认不配置 `CORS_ORIGINS` 时不限制跨域；若前端与 API 不同域且需收紧来源，再设置白名单（逗号分隔，如 `http://192.168.1.10:8080`）。

### 使用 GHCR 预构建镜像

推送 Git 标签 `v*` 后，GitHub Actions 会自动构建并推送镜像到 [GitHub Container Registry](https://docs.github.com/zh/packages/working-with-a-github-packages-registry/working-with-the-container-registry)：

| 说明 | 示例 |
|------|------|
| 单镜像（前后端一体） | `ghcr.io/<owner>/mistake-notebook:v1.0.0` |

标签 `v1.0.0` 会解析为应用版本 `1.0.0`，并同时打上 `v1.0.0`、`1.0.0`、`latest` 三个镜像标签。

发布示例：

```bash
git tag v1.0.0
git push origin v1.0.0
```

在仓库 **Actions** 查看构建进度；镜像位于 **Packages**。若需公开拉取，请在 GHCR 将对应包设为 **Public**。

## CI/CD

工作流文件：`.github/workflows/docker-publish.yml`

- **触发条件**：推送符合 `v*` 的 Git 标签
- **构建内容**：`docker/Dockerfile`（多阶段：前端构建 + Python + Nginx + `tini` 进程管理）
- **版本注入**：构建参数 `APP_VERSION` / `VITE_APP_VERSION`（去掉标签前缀 `v`）
- **推送目标**：`ghcr.io`，使用 `GITHUB_TOKEN` 登录

## 项目结构

```
mistake-notebook/
├── backend/           # FastAPI 应用
├── frontend/          # Vue 3 前端
├── docker/            # Dockerfile、Nginx 配置
├── .github/workflows/ # GitHub Actions
└── docker-compose.yml
```

## 技术栈

- **前端**：Vue 3、Vite、TypeScript、Vue Router、Pinia、Naive UI、Apache ECharts、Axios
- **后端**：FastAPI、SQLAlchemy 2（async）、aiosqlite、httpx、cryptography

## 安全提示

- 生产环境务必修改 `APP_SECRET` 与管理员默认密码。
- API Key 经加密后存库，请勿将 `.env` 或数据库文件提交到版本库。
