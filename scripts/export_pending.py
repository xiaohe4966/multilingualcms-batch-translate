#!/usr/bin/env python3
"""导出翻译记忆库里待翻译的条目（translated 为空）"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

from common import connect, load_config, query, table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--out", default="pending.json")
    ap.add_argument("--lang", help="只导出某个目标语言")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = connect(cfg)
    t = table(cfg, "translate_memory")

    sql = f"SELECT id, src_hash, src_text, from_lang, to_lang, use_translate FROM {t} WHERE (translated IS NULL OR translated = '')"
    if args.lang:
        sql += f" AND to_lang = '{args.lang}'"
    rows = query(conn, sql)

    items = [
        {
            "id": r["id"],
            "src_text": r["src_text"],
            "from_lang": r["from_lang"],
            "to_lang": r["to_lang"],
            "use_translate": r["use_translate"],
        }
        for r in rows
    ]

    by_lang = defaultdict(list)
    for it in items:
        by_lang[it["to_lang"]].append(it)

    print(f"待翻译条目: {len(items)} 条，覆盖 {len(by_lang)} 个目标语言")
    for lang, lst in sorted(by_lang.items()):
        uniq = len({x["src_text"] for x in lst})
        print(f"  {lang}: {len(lst)} 条（唯一原文 {uniq} 条）")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print(f"已导出: {args.out}")


if __name__ == "__main__":
    main()
