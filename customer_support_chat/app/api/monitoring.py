from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import psutil
import time

router = APIRouter(prefix="/metrics", tags=["monitoring"])

# 系统启动时间
START_TIME = time.time()

@router.get("/prometheus")
async def metrics():
    """Prometheus指标端点"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "uptime_seconds": time.time() - START_TIME,
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent
    }

@router.get("/stats")
async def get_stats():
    """获取实时统计数据（供前端Dashboard使用）"""
    from prometheus_client import REGISTRY
    
    stats = {}
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            stats[sample.name] = {
                "value": sample.value,
                "labels": sample.labels
            }
    
    return {
        "timestamp": time.time(),
        "uptime": time.time() - START_TIME,
        "metrics": stats
    }