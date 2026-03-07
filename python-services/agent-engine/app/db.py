"""
app/db.py — 数据库连接辅助模块
"""
from __future__ import annotations

import os
import pymysql
from pymysql.cursors import DictCursor


def get_db_connection():
    """获取 MySQL 数据库连接"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "nexus"),
        password=os.getenv("MYSQL_PASS", "nexus_pass"),
        database=os.getenv("MYSQL_DB", "nexus_agent"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
