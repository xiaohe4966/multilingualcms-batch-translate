"""多语言CMS批量翻译流水线 - 公共工具

配置来源优先级：命令行 --config > 环境变量 MC_* > 技能目录下 config.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import pymysql
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip3 install pymysql")

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_ROOT / "config.json"
EXAMPLE_CONFIG = SKILL_ROOT / "config.example.json"

ENV_MAP = {
    "db.host": "MC_DB_HOST",
    "db.port": "MC_DB_PORT",
    "db.user": "MC_DB_USER",
    "db.password": "MC_DB_PASSWORD",
    "db.database": "MC_DB_DATABASE",
    "db.prefix": "MC_DB_PREFIX",
    "site.base_url": "MC_SITE_BASE_URL",
    "site.admin_path": "MC_ADMIN_PATH",
    "site.http_auth": "MC_HTTP_AUTH",
    "site.cookie": "MC_COOKIE",
}


def _deep_update(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        cfg_path = EXAMPLE_CONFIG
        print(f"[warn] 未找到 config.json，使用示例配置（{cfg_path}）", file=sys.stderr)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for dotted, env in ENV_MAP.items():
        if env in os.environ:
            section, key = dotted.split(".", 1)
            val = os.environ[env]
            if key == "port":
                val = int(val)
            cfg.setdefault(section, {})[key] = val
    return cfg


def connect(cfg: dict):
    db = cfg["db"]
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def query(conn, sql: str, params=None) -> list[dict]:
    """执行 SELECT，返回字典列表"""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def execute(conn, sql: str, params=None) -> int:
    """执行写操作，返回影响行数"""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def table(cfg: dict, name: str) -> str:
    """带前缀的表名"""
    return f"{cfg['db'].get('prefix', 'fa_')}{name}"


def main_lang(cfg: dict, conn) -> str:
    """站点主语言（默认 en）"""
    rows = query(
        conn,
        f"SELECT value FROM {table(cfg, 'config')} WHERE name = 'default_weblang' LIMIT 1",
    )
    row = rows[0] if rows else None
    if row and row.get("value"):
        return row["value"]
    return "en"


def normalized(text: str) -> str:
    """与站点清洗逻辑一致：去首尾空格 + 合并连续空白"""
    return " ".join(str(text).split())


def src_hash(text: str) -> str:
    import hashlib

    return hashlib.md5(normalized(text).encode("utf-8")).hexdigest()
