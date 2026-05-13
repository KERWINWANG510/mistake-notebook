# AI 错题本

Vue 3 + Naive UI 前端，FastAPI + SQLite 后端，支持拍照/上传识别、错题管理、科目与年级管理、可配置多家 OpenAI 兼容 AI。

## 本地开发

### 后端

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

可选环境变量（`.env` 或系统环境）：

- `APP_SECRET`：用于加密存储 API Key，生产环境务必修改。
- `DATABASE_URL`：默认 `sqlite+aiosqlite:///./data/app.db`。
- `UPLOAD_DIR`：上传图片目录，默认 `./data/uploads`。
- `CORS_ORIGINS`：逗号分隔的前端源，默认包含 `http://localhost:5173`。
- `ACCESS_TOKEN_EXPIRE_MINUTES`：JWT 有效期（分钟），默认 7 天。

### 登录与账号

- 首次启动会自动创建内置管理员：**用户名 `admin`，密码 `123456`**（请在生产环境登录后立即修改密码或自行扩展改密功能）。
- 仅 **admin** 可通过「用户管理」页面或 `POST /api/auth/users` 创建其他账号；普通用户不能建号。
- 除 `/api/health` 与登录接口外，其余 API 需在请求头携带 `Authorization: Bearer <token>`。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`，通过 Vite 代理转发 `/api` 到后端。

生产构建：`npm run build`，产物在 `frontend/dist`。部署到 NAS 时可将 `VITE_API_BASE` 留空，由 Nginx 同域反代 `/api`。

## Docker（NAS）

在项目根目录：

```powershell
docker compose up -d --build
```

- 前端：`http://localhost:8080`（Nginx 托管静态页并反代 `/api`）。
- 后端：`http://localhost:8000`（也可只对内网开放，由 Nginx 代理）。

数据与上传文件在卷 `mistake_data`（容器内 `/data`）。首次部署请设置环境变量 `APP_SECRET`。

若通过局域网 IP 访问 Web，请在 `CORS_ORIGINS` 中加入对应源（例如 `http://192.168.1.10:8080`），否则浏览器会拦截跨域。

## 功能说明（当前版本）

- **登录**：JWT；内置管理员 `admin` / `123456`；管理员可创建子账号；错题与 AI 配置按登录用户隔离使用（AI 配置仍为全局一套激活配置，可按需再改为按用户）。
- **错题**：列表筛选、录入（识图模型 OCR 题干 + 解题模型生成思路/答案/科目年级推荐）、详情编辑、**更换题目配图**；保存原始图片；图片通过鉴权接口拉取（非匿名 URL）。
- **科目 / 年级**：同前。
- **AI**：内置厂商含 **阿里百炼（OpenAI 兼容）** 等；可配置 **默认模型**、**识图专用模型**、**解题专用模型**（后两者可空，空则回退到默认）；支持拉取模型列表与激活配置。
## 技术栈

- 前端：Vue 3、Vite、TypeScript、Vue Router、Pinia、Naive UI（`unplugin-vue-components` 按需引入）、Axios。
- 后端：FastAPI、SQLAlchemy 2（async）、aiosqlite、httpx、cryptography。
