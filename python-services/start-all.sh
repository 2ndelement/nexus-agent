#!/bin/bash
# 统一启动所有 Python 服务并注册到 Nacos

export NACOS_ENABLED=true
export NACOS_SERVER=127.0.0.1:8848
export SANDBOX_DISABLE_LIMITS=1  # cgroup v2 兼容

echo "=== 启动 Python 服务（Nacos 模式）==="

# 停止现有服务
echo "停止现有服务..."
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "uvicorn.*8001" 2>/dev/null || true
sleep 2

# 启动 sandbox-service
echo "启动 sandbox-service (8020)..."
cd /root/nexus-agent/python-services/sandbox-service
nohup python main.py > /tmp/sandbox-service.log 2>&1 &

# 启动 agent-engine
echo "启动 agent-engine (8001)..."
cd /root/nexus-agent/python-services/agent-engine
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8001 > /tmp/agent-engine.log 2>&1 &

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo -e "\n=== 服务状态 ==="
curl -s http://localhost:8020/health && echo ""
curl -s http://localhost:8001/health && echo ""

# 检查 Nacos 注册
echo -e "\n=== Nacos 已注册服务 ==="
curl -s "http://localhost:8848/nacos/v1/ns/service/list?pageNo=1&pageSize=20" 2>/dev/null

echo -e "\n\n启动完成！"
