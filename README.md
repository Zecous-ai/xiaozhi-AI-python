# Xiaozhi ESP32 Server (Python)

本仓库为 `xiaozhi-esp32-server-java` 的 Python 重构版本，后端采用 FastAPI，前端保留原 Vue 项目并由后端托管静态资源。

## 本地运行

1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

2. 运行服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8091
```

3. 初始化数据库

使用原 Java 项目中的 `db/init.sql` 初始化 MySQL。

## Docker 运行

```bash
docker-compose up -d --build
```

## 说明

- API 路径保持 `/api/*` 不变。
- WebSocket 路径保持 `/ws/xiaozhi/v1/` 不变。
- 仍沿用原 MySQL/Redis schema。

## 已知限制

- 语音链路目前仅实现基础文本对话，音频识别/播放能力待进一步完善。
- 部分第三方供应商（如短信、部分 TTS/STT）未完成完整对接，需要按实际配置扩展。
