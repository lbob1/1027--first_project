"""MinIO 对象存储封装（M-S2-T01）。

- 连接与凭据从 get_settings() 读取（MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/BUCKET），
  懒创建单例（与 app.core.db.get_engine 风格一致）；模块导入不建连接；
- object key 按 workspace 隔离组织（细则 1）：
  {workspace_id}/{document_id}/v{version_no}/{filename}——三维齐备，
  避免跨区对象混放；file_path 语义只存 object key（P-S2 硬性约束）；
- 任何日志不输出 SECRET_KEY / ACCESS_KEY（细则 9）。
"""

import io
import logging
import uuid

from functools import lru_cache

from minio import Minio

from app.core.config import get_settings

log = logging.getLogger("app.services.storage")


@lru_cache
def get_client() -> Minio:
    """懒创建全局 Minio 客户端（本地开发 secure=False，无 TLS）。"""
    s = get_settings()
    return Minio(
        s.MINIO_ENDPOINT,  # 形如 localhost:9000，不含 scheme
        access_key=s.MINIO_ACCESS_KEY,
        secret_key=s.MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket() -> str:
    """bucket 不存在则创建（幂等，服务启动时调用）。返回 bucket 名。"""
    client = get_client()
    s = get_settings()
    if not client.bucket_exists(s.MINIO_BUCKET):
        client.make_bucket(s.MINIO_BUCKET)
        log.info("bucket created name=%s", s.MINIO_BUCKET)
    return s.MINIO_BUCKET


def build_object_key(
    workspace_id: uuid.UUID, document_id: uuid.UUID, version_no: int, filename: str
) -> str:
    """object key 命名规则：{workspace_id}/{document_id}/v{version_no}/{filename}。"""
    return f"{workspace_id}/{document_id}/v{version_no}/{filename}"


def put_object(
    workspace_id: uuid.UUID, document_id: uuid.UUID, version_no: int,
    data: bytes, filename: str,
) -> str:
    """上传原始文件字节，返回 object key（即 document_versions.file_path 的值）。"""
    client = get_client()
    key = build_object_key(workspace_id, document_id, version_no, filename)
    client.put_object(
        get_settings().MINIO_BUCKET, key, io.BytesIO(data), length=len(data)
    )
    log.info("object put key=%s bytes=%d", key, len(data))
    return key


def get_object(object_key: str) -> bytes:
    """按 object key 取回原始文件字节。"""
    resp = get_client().get_object(get_settings().MINIO_BUCKET, object_key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def list_object_keys(prefix: str = "") -> list[str]:
    """列出 bucket 内指定前缀的全部 object key（验证/运维用）。"""
    client = get_client()
    return [
        obj.object_name
        for obj in client.list_objects(get_settings().MINIO_BUCKET, prefix=prefix, recursive=True)
    ]


def remove_object(object_key: str) -> None:
    """删除单个对象（测试清理/失效数据清理用）。"""
    get_client().remove_object(get_settings().MINIO_BUCKET, object_key)
    log.info("object removed key=%s", object_key)
