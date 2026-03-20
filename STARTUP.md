# Skyline 启动说明书

服务器 IP：`10.31.112.43`

---

## 问题根因说明

### 问题 1：`ModuleNotFoundError: No module named 'routers'`

`backend/main.py` 使用的是**相对于 `backend/` 目录的绝对导入**（`from routers.video_stream import router`）。

如果你在 `~/skyline` 根目录直接执行 `uvicorn backend.main:app`，Python 的 `sys.path` 里没有 `backend/`，所以找不到 `routers` 模块。

**解法**：必须先 `cd backend/`，再执行 `uvicorn main:app`。启动脚本已经自动处理这一步。

---

### 问题 2：WebSocket "Localhost 陷阱"（已确认无此问题）

`frontend/src/composables/useWebSocket.ts` 第 14-15 行：

```typescript
const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ??
  `ws://${window.location.hostname}:8000/api/ws/video_stream`
```

`window.location.hostname` 是**浏览器运行时动态读取当前页面所在的主机名**。

- 你的 Mac 浏览器访问 `http://10.31.112.43:5173` → `hostname = 10.31.112.43`
- WebSocket 自动连接 `ws://10.31.112.43:8000/api/ws/video_stream` ✓

没有硬编码 localhost，不需要改动。

---

### 问题 3：Vite 默认只监听 127.0.0.1（已修复）

`npm run dev` 默认只绑定 `127.0.0.1`，外部的 Mac 无法访问。

已在 `vite.config.ts` 加入 `host: '0.0.0.0'`，现在监听所有网卡。

---

## 启动步骤

> 需要两个终端窗口，分别运行后端和前端。

### 终端 1 — 启动后端 (FastAPI)

```bash
# 方法 A：使用启动脚本（推荐，在任意目录执行）
cd ~/skyline
bash start_backend.sh

# 方法 B：手动（必须先 cd 进 backend/）
cd ~/skyline/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后你会看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

验证后端是否正常：在服务器或 Mac 上访问 `http://10.31.112.43:8000/health`，应返回：

```json
{"status": "ok", "service": "skyline-backend", "version": "1.0.0"}
```

---

### 终端 2 — 启动前端 (Vue3 + Vite)

```bash
# 方法 A：使用启动脚本（推荐）
cd ~/skyline
bash start_frontend.sh

# 方法 B：手动
cd ~/skyline/frontend
npm run dev
```

启动成功后你会看到：

```
  VITE v8.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://10.31.112.43:5173/   ← Mac 用这个地址
```

---

## 在 Mac 上访问

打开 Safari / Chrome，输入：

```
http://10.31.112.43:5173
```

页面加载后：
- 左侧面板 WebSocket 状态灯变绿（`ONLINE`）表示连接成功
- 点击 **DROP ZONE** 上传一段本地视频，或点击 **LIVE CAM** 开启摄像头
- 右侧 Canvas 开始渲染视频画面，并显示 AI 检测框

---

## 数据流确认（跨设备场景）

```
Mac 浏览器
    │
    ├─ HTTP  → http://10.31.112.43:5173   (Vite 前端服务)
    │
    └─ WS   → ws://10.31.112.43:8000/api/ws/video_stream  (FastAPI 后端)
                          │
                    window.location.hostname
                    动态解析为 10.31.112.43
                    （不是 localhost）
```

两个端口都绑定在 `0.0.0.0`，防火墙允许即可访问。

---

## 防火墙检查（如果无法连接）

```bash
# 检查端口是否在监听
ss -tlnp | grep -E '8000|5173'

# 临时开放端口（如果用 ufw）
sudo ufw allow 8000
sudo ufw allow 5173
```

---

## 文件结构速查

```
~/skyline/
├── start_backend.sh     ← 一键启动后端（自动 cd 到 backend/）
├── start_frontend.sh    ← 一键启动前端
├── backend/
│   ├── main.py          ← FastAPI 入口（必须从此目录运行）
│   ├── core/
│   │   ├── models.py    ← Pydantic 数据模型
│   │   └── inference.py ← LIFO 推理调度器
│   └── routers/
│       └── video_stream.py  ← WebSocket /api/ws/video_stream
└── frontend/
    ├── vite.config.ts   ← host: 0.0.0.0，允许外部访问
    └── src/
        └── composables/
            └── useWebSocket.ts  ← WS URL 用 window.location.hostname 动态生成
```
