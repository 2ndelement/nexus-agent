"""
app/api/v1/media.py — 文件访问代理

提供对沙箱工作区文件的 HTTP 访问代理，
解决浏览器无法直接访问 sandbox service 的问题。
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["media"])

# 工作区根目录（与 sandbox service 共享）
WORKSPACE_ROOT = os.getenv("SANDBOX_WORKSPACE_ROOT", "/data/sandbox")


@router.get("/{owner_type}/{owner_id}/{conversation_id}/{filename}")
async def get_media_file(
    owner_type: str,
    owner_id: str,
    conversation_id: str,
    filename: str,
):
    """
    获取沙箱工作区文件。

    路径格式：/api/v1/media/{owner_type}/{owner_id}/{conversation_id}/{filename}
    示例：/api/v1/media/PERSONAL/17/conv123/chart.png

    Returns:
        - 200: 文件内容
        - 404: 文件不存在
    """
    # 构建文件路径
    file_path = os.path.join(WORKSPACE_ROOT, owner_type, owner_id, conversation_id, filename)

    # 安全检查：防止路径遍历
    real_root = os.path.realpath(WORKSPACE_ROOT)
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(real_root):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=guess_mime_type(filename),
    )


def guess_mime_type(filename: str) -> str:
    """根据扩展名猜测 MIME 类型"""
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"
