#!/usr/bin/env python3
"""多语言CMS 一致性检查（可自动修复部分问题）

检查项：
  1. fa_multilingualcms_web.lang 与 fa_translate_lang.lang 是否一致（不一致→批量翻译会报「找不到语言配置」）
  2. fa_fanyi_tables.fanyi_fields 里的字段是否真实存在于对应表（不存在→整批 500）
  3. 各内容表的 cate_id 是否指向同语言栏目（串号→可修复）
  4. fa_multilingualcms_cate.parent_id 是否指向同语言父栏目（串号→可修复）
  5. 内容里是否残留「待翻译」占位
  6. 翻译记忆库还有多少待译条目
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from common import connect, execute, load_config, main_lang, query, table

PLACEHOLDER = "待翻译"
TEXT_COLS = [
    "name", "seotitle", "keywords", "description", "abstract", "byname",
    "title", "btitle", "content", "value", "bannermsa", "bannermsb",
]


def columns(conn, tbl: str) -> list[str]:
    rows = query(conn, 
        "SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s",
        (tbl,),
    )
    return [r["column_name"] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--fix", action="store_true", help="自动修复 cate_id / parent_id 串号")
    ap.add_argument("--lang-dir", help="语言包目录（形如 application/multilingualcms/lang），检查词条缺失")
    ap.add_argument("--view-dir", help="模板目录，检查 lang('xxx') 用到的词条是否都在语言包里")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = connect(cfg)
    p = cfg["db"].get("prefix", "fa_")
    ml = main_lang(cfg, conn)
    issues = 0

    # ---------- 1. 站点语言代码 vs 语言字典 ----------
    print("== 1. 站点语言代码 vs fa_translate_lang.lang")
    web = query(conn, f"SELECT id, lang, name FROM {table(cfg,'multilingualcms_web')} ORDER BY id")
    dict_rows = query(conn, f"SELECT lang FROM {table(cfg,'translate_lang')} WHERE lang IS NOT NULL AND lang <> ''")
    dict_langs = {r["lang"] for r in dict_rows}
    missing = [w for w in web if w["lang"] and w["lang"] not in dict_langs]
    if missing:
        issues += len(missing)
        for w in missing:
            print(f"  ! web.id={w['id']} lang={w['lang']} ({w['name']}) 在语言字典里没有对应行")
        print("  → 修正：把 web.lang 改成字典里的代码（字典列 lang，引擎代码在 baidu/tencent/google 等列）")
    else:
        print("  正常")

    # ---------- 2. fanyi_fields 字段是否存在 ----------
    print("== 2. fa_fanyi_tables.fanyi_fields 字段存在性")
    ft = query(conn, f"SELECT id, table_name, fanyi_fields FROM {table(cfg,'fanyi_tables')}")
    bad_fields = 0
    for r in ft:
        cols = columns(conn, r["table_name"])
        if not cols:
            print(f"  ! 表不存在: {r['table_name']}")
            issues += 1
            bad_fields += 1
            continue
        bad = [f for f in (x.strip() for x in (r["fanyi_fields"] or "").split(",")) if f and f not in cols]
        if bad:
            issues += len(bad)
            bad_fields += len(bad)
            keep = ",".join(f for f in (x.strip() for x in (r["fanyi_fields"] or "").split(",")) if f and f not in bad)
            print(f"  ! {r['table_name']} 的 fanyi_fields 含不存在的列: {', '.join(bad)}")
            print(f"    → 修正: UPDATE {table(cfg,'fanyi_tables')} SET fanyi_fields='{keep}' WHERE id={r['id']}")
    if not bad_fields:
        print("  正常")

    # ---------- 3. cate_id 串号 ----------
    print("== 3. 内容表 cate_id 跨语言串号")
    cates = {}
    for r in query(conn, f"SELECT id, lang, copy_id, parent_id, name FROM {table(cfg,'multilingualcms_cate')}"):
        cates[r["id"]] = r
    by_lang_copy = {}
    for c in cates.values():
        by_lang_copy[(c["lang"], c["copy_id"])] = c["id"]

    cate_tables = [r["table_name"] for r in query(conn, 
        "SELECT table_name FROM information_schema.columns WHERE table_schema = DATABASE() AND column_name = 'cate_id'"
    )]

    fixed = 0
    any_cate_bad = False
    for tbl in cate_tables:
        bad = []
        for r in query(conn, f"SELECT id, lang, cate_id FROM `{tbl}` WHERE cate_id > 0"):
            if r["lang"] == ml:
                continue
            cur = cates.get(r["cate_id"])
            if not cur:
                continue
            src_id = cur["id"] if cur["lang"] == ml else int(cur["copy_id"] or 0)
            if src_id <= 0:
                continue
            target = by_lang_copy.get((r["lang"], src_id))
            if target and target != r["cate_id"]:
                bad.append((r["id"], r["lang"], r["cate_id"], target))
        if bad:
            any_cate_bad = True
            issues += len(bad)
            groups = defaultdict(list)
            for b in bad:
                groups[(b[1], b[2], b[3])].append(b[0])
            print(f"  ! {tbl}: {len(bad)} 条串号")
            for (lang, old, new), ids in sorted(groups.items()):
                print(f"      {lang}: cate_id {old} → {new}（{len(ids)} 条，id {ids[0]}..{ids[-1]}）")
            if args.fix:
                for b in bad:
                    execute(conn, f"UPDATE `{tbl}` SET cate_id = %s WHERE id = %s", (b[3], b[0]))
                fixed += len(bad)
                print(f"      已修复 {len(bad)} 条")
    if fixed:
        print(f"  共修复 {fixed} 条")
    if not any_cate_bad:
        print("  正常")

    # ---------- 4. cate.parent_id 串号 ----------
    print("== 4. fa_multilingualcms_cate.parent_id 跨语言串号")
    bad_parent = []
    for c in cates.values():
        if c["lang"] == ml:
            continue
        src = cates.get(c["copy_id"])
        if not src or src["lang"] != ml:
            continue
        sp = int(src["parent_id"] or 0)
        if sp <= 0:
            continue
        target = by_lang_copy.get((c["lang"], sp))
        if target and target != int(c["parent_id"] or 0):
            bad_parent.append((c["id"], c["lang"], c["parent_id"], target))
    if bad_parent:
        issues += len(bad_parent)
        print(f"  ! {len(bad_parent)} 条 parent_id 串号")
        for b in bad_parent:
            print(f"      #{b[0]} {b[1]} parent_id {b[2]} → {b[3]}")
        if args.fix:
            for b in bad_parent:
                execute(conn, f"UPDATE {table(cfg,'multilingualcms_cate')} SET parent_id = %s WHERE id = %s", (b[3], b[0]))
            print(f"      已修复 {len(bad_parent)} 条")
    else:
        print("  正常")

    # ---------- 5. 残留占位 ----------
    print("== 5. 内容表残留「待翻译」占位")
    any_ph = False
    for t in query(conn, 
        "SELECT table_name FROM information_schema.columns WHERE table_schema = DATABASE() AND column_name = 'lang'"
    ):
        name = t["table_name"]
        if "translate_lang" in name or "fanyi" in name or name.startswith(p + "config") or name.startswith(p + "user"):
            continue
        cols = [c for c in columns(conn, name) if c in TEXT_COLS]
        if not cols:
            continue
        cond = " OR ".join(f"`{c}` LIKE %s" for c in cols)
        n = query(conn, f"SELECT COUNT(*) n FROM `{name}` WHERE {cond}", tuple(["%" + PLACEHOLDER + "%"] * len(cols)))[0]["n"]
        if n:
            any_ph = True
            issues += n
            print(f"  ! {name}: {n} 行仍含占位（填好记忆库后重跑一次批量翻译即可覆盖）")
    if not any_ph:
        print("  正常")

    # ---------- 6. 记忆库待译 ----------
    print("== 6. 翻译记忆库待译条目")
    row = query(conn, f"SELECT COUNT(*) n FROM {table(cfg,'translate_memory')} WHERE translated IS NULL OR translated = ''")[0]
    print(f"  待译 {row['n']} 条")
    if row["n"]:
        issues += row["n"]

    # ---------- 7. 语言包词条 ----------
    if args.lang_dir:
        print("== 7. 语言包词条完整性")
        lang_dir = Path(args.lang_dir)
        en_file = lang_dir / ml / "index.php"
        if not en_file.exists():
            en_file = lang_dir / "en" / "index.php"
        if not en_file.exists():
            print(f"  ! 找不到主语言包: {en_file}")
        else:
            en_text = en_file.read_text(encoding="utf-8")
            keys = set(re.findall(r"'((?:[^'\\]|\\.)*)'\s*=>", en_text))
            used = set()
            if args.view_dir:
                for pth in Path(args.view_dir).rglob("*.html"):
                    used |= set(re.findall(r"lang\('([^']+)'\)", pth.read_text(encoding="utf-8", errors="ignore")))
            miss = sorted(k for k in used if k not in keys)
            if miss:
                issues += len(miss)
                print(f"  ! 模板用到但语言包里没有的词条 ({len(miss)}): {', '.join(miss)}")
                print("     → 在主语言包里补上英文，再重新生成各语言语言包")
            elif used:
                print("  正常")
            else:
                print("  未提供 --view-dir，跳过模板比对")

    print(f"\n共发现 {issues} 个问题" + ("（已按 --fix 修复可自动修复项）" if args.fix else "（加 --fix 自动修复可修项）"))


if __name__ == "__main__":
    main()
