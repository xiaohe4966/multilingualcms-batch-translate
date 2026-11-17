#!/usr/bin/env python3
"""把译文写回翻译记忆库 fa_translate_memory

输入 JSON 格式（二选一）：
  [{"src_text": "...", "to_lang": "de", "from_lang": "en", "translated": "..."}, ...]
  {"de": {"原文": "译文", ...}, "fr": {...}}          # 按目标语言分组的字典
"""
from __future__ import annotations

import argparse
import json
import sys

from common import connect, load_config, normalized, src_hash, table


def flatten(data) -> list[dict]:
    out = []
    if isinstance(data, dict):
        for to_lang, mapping in data.items():
            if isinstance(mapping, dict):
                for src, tr in mapping.items():
                    out.append({"src_text": src, "to_lang": to_lang, "from_lang": "auto", "translated": tr})
            else:
                out.append(mapping)
    else:
        out = list(data)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    data = json.loads(open(args.infile, encoding="utf-8").read())
    items = flatten(data)

    conn = connect(cfg)
    t = table(cfg, "translate_memory")

    sel = conn.cursor()
    upd = conn.cursor()
    ins = conn.cursor()

    ok = miss = empty = 0
    for it in items:
        src = str(it.get("src_text", ""))
        to_lang = it.get("to_lang", "")
        from_lang = it.get("from_lang") or "auto"
        tr = it.get("translated")
        if tr is None or str(tr).strip() == "":
            empty += 1
            continue
        tr = str(tr)
        h = src_hash(src)
        sel.execute(
            f"SELECT id FROM {t} WHERE src_hash = %s AND from_lang = %s AND to_lang = %s ORDER BY id",
            (h, from_lang, to_lang),
        )
        row = sel.fetchone()
        if row:
            if not args.dry_run:
                upd.execute(
                    f"UPDATE {t} SET translated = %s, md5 = %s, updatetime = UNIX_TIMESTAMP() WHERE id = %s",
                    (tr, src_hash(tr), row["id"]),
                )
            ok += 1
        else:
            # 记忆库里没有这条：新增一条（用于补齐翻译记忆库）
            if not args.dry_run:
                ins.execute(
                    f"INSERT INTO {t} (src_hash, src_text, from_lang, to_lang, translated, use_translate,"
                    f" createtime, updatetime, md5) VALUES (%s,%s,%s,%s,%s,'manual',UNIX_TIMESTAMP(),UNIX_TIMESTAMP(),%s)",
                    (h, normalized(src), from_lang, to_lang, tr, src_hash(tr)),
                )
            ok += 1
    print(f"处理 {len(items)} 条：写入/更新 {ok} 条，空译文跳过 {empty} 条" + ("（dry-run，未落库）" if args.dry_run else ""))
    if miss:
        print(f"未匹配 {miss} 条", file=sys.stderr)


if __name__ == "__main__":
    main()
