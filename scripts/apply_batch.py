#!/usr/bin/env python3
"""调用后台批量翻译接口，把记忆库里的真实译文回填到内容表

前提：记忆库已填好译文（translated<>''），且站点的「预先假翻译」已关闭。
用法：
  python3 scripts/apply_batch.py --dry-run     # 只列出将要处理的表
  python3 scripts/apply_batch.py                # 实际执行
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode

from common import connect, load_config, query, table


def post(cfg: dict, path: str, data: dict) -> tuple[int, str]:
    base = cfg["site"]["base_url"].rstrip("/")
    url = base + path
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    req.add_header("X-Requested-With", "XMLHttpRequest")
    auth = cfg["site"].get("http_auth")
    if auth:
        raw = auth if ":" in auth else f"{auth}:"
        req.add_header("Authorization", "Basic " + b64encode(raw.encode()).decode())
    cookie = cfg["site"].get("cookie")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=cfg["site"].get("timeout", 600)) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--admin-path", help="后台入口，如 myadmin.php")
    ap.add_argument("--controller", default="multilingualcms", help="要翻译的模块，如 multilingualcms")
    ap.add_argument("--tables", help="要翻译的表名（对应后台控制器），逗号分隔；默认按 fa_fanyi_tables 推断")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    admin = args.admin_path or cfg["site"].get("admin_path", "myadmin.php")
    conn = connect(cfg)
    p = cfg["db"].get("prefix", "fa_")

    # 可翻译的表 -> 后台控制器名（news->news, cate->cate, pro->pro ...）
    rows = query(conn, f"SELECT table_name, fanyi_fields FROM {table(cfg,'fanyi_tables')} ORDER BY id")
    targets = []
    for r in rows:
        name = r["table_name"]
        short = name[len(p):] if name.startswith(p) else name
        short = short.replace("multilingualcms_", "")
        targets.append((short, name, r["fanyi_fields"]))

    if args.tables:
        want = {x.strip() for x in args.tables.split(",")}
        targets = [t for t in targets if t[0] in want]

    # 目标语言：站点语言表里开启的、且不是主语言
    ml = "en"
    row = query(conn, f"SELECT value FROM {table(cfg,'config')} WHERE name='default_weblang' LIMIT 1").fetchone()
    if row and row["value"]:
        ml = row["value"]
    langs = [
        r["lang"]
        for r in query(conn, f"SELECT lang FROM {table(cfg,'multilingualcms_web')} WHERE switch = 1 AND lang <> %s", (ml,))
    ]
    print(f"主语言 {ml}，目标语言: {', '.join(langs)}")

    for short, full, fields in targets:
        ids = [
            r["id"]
            for r in query(conn, f"SELECT id FROM `{full}` WHERE lang = %s", (ml,))
        ]
        if not ids:
            print(f"  {short}: 无主语言数据，跳过")
            continue
        print(f"  {short}: 主语言 {len(ids)} 条 -> {len(langs)} 个语言；字段 {fields}")
        if args.dry_run:
            continue
        path = f"/{admin}/{args.controller}/{short}/translation/ids/{','.join(map(str, ids))}?dialog=1"
        data = {
            "table": full,
            "langs_text": "",
            "langs": ",".join(langs),
            "ids": ",".join(map(str, ids)),
            "fields": fields,
        }
        status, body = post(cfg, path, data)
        print(f"      HTTP {status}: {body.strip()[:160]}")


if __name__ == "__main__":
    main()
