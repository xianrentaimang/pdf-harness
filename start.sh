#!/bin/bash
# PDF → Markdown 转换服务 启动脚本（默认端口 16082）
cd "$(dirname "$0")"
PORT=${PORT:-16082}
PY=/home/hz1/miniconda3/envs/openclaw/bin/python3
[ -x "$PY" ] || PY=python3
mkdir -p logs

case "$1" in
  stop)
    if [ -f logs/app.pid ]; then
      kill "$(cat logs/app.pid)" 2>/dev/null
      rm -f logs/app.pid
      echo "已停止 (port $PORT)"
    else
      echo "未在运行"
    fi
    ;;
  restart)
    "$0" stop; sleep 1; exec "$0"
    ;;
  *)
    if [ -f logs/app.pid ] && kill -0 "$(cat logs/app.pid)" 2>/dev/null; then
      echo "已在运行 PID=$(cat logs/app.pid) port=$PORT"
      exit 0
    fi
    PORT=$PORT nohup "$PY" app.py > logs/app.log 2>&1 &
    echo $! > logs/app.pid
    sleep 2
    echo "已启动 (port $PORT) PID=$(cat logs/app.pid)"
    echo "访问: http://<IP>:$PORT/"
    ;;
esac
