# Xiaozhi ESP32 Server (Python)

本仓库是 `xiaozhi-esp32-server-java` 的 Python 重构版，后端采用 FastAPI，前端保留原 Vue 项目并由后端托管静态资源。协议、接口与 Java 版保持一致。

## 功能概览

- API 路径保持 `/api/*` 不变
- WebSocket 路径保持 `/ws/xiaozhi/v1/` 不变
- LLM + Function Call + MCP + IoT
- STT / TTS / VAD 多厂商适配（与 Java 版配置一致）
- 语音音频合并与消息入库

## 环境要求

- Python 3.11+
- MySQL 8.x
- Redis 7.x
- FFmpeg + Opus
  - Windows: 安装 ffmpeg，并确保 `ffmpeg` 在 PATH 中
  - Linux: `apt-get install -y ffmpeg libopus0 libopusfile0`
- Vosk 模型
  - 下载 Vosk 模型到 `backend/models/vosk-model`（或设置 `VOSK_MODEL_PATH`）
- Silero VAD 模型
  - 已内置 `backend/models/silero_vad.onnx`

## 本地运行（Windows / Linux）

1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

2. 配置环境变量

复制 `backend/.env.example` 为 `backend/.env`，按需修改数据库、Redis、模型路径等配置。

3. 初始化数据库

使用 Java 项目中的 `db/init.sql` 初始化 MySQL。

4. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8091
```

## Docker 部署

```bash
docker-compose up -d --build
```

默认会映射端口 `8091`，并把 `./audio` 挂载到容器内用于音频持久化。

## 说明

- Web 资源目录：`web/`，构建后的静态资源会被后端托管
- 语音文件默认输出到 `audio/`（可通过 `AUDIO_PATH` 调整）
- 其余配置与 Java 版保持一致（见 `backend/.env.example`）
