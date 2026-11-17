# 多语言CMS 批量翻译流水线（multilingualcms-batch-translate）

把 FastAdmin 多语言 CMS（[MultilingualCMS](https://gitee.com/xiaohe4966/MultilingualCMS)）的批量翻译做成一条可复用的流水线：

```
开启「预先假翻译」 → 后台批量翻译（原文进翻译记忆库，内容写占位）
        ↓
导出记忆库待译条目 → AI / 翻译引擎翻译 → 写回 translate_memory.translated
        ↓
关闭「预先假翻译」 → 再点一次批量翻译 → 命中记忆库，内容回填真实译文
        ↓
一致性复核：语言代码 / cate_id 串号 / 字段配置 / 语言包词条 / 表单必填
```

## 特点

- 不依赖任何站点私有脚本：全部通过 MySQL + 后台已有接口完成，**不需要往服务器上传 PHP 文件**。
- 翻译质量可人工介入：短 UI 文案、交���段落可由 LLM 校对后写回记忆库。
- 自带一致性体检：能提前发现"语言代码对不上""字段不存在""cate_id 串语言"这类会让整批翻译 500 或写脏数据的坑。

## 目录

```
SKILL.md                      技能主文档（工作流与坑位）
config.example.json           配置模板（复制为 config.json 使用）
scripts/
  common.py                   配置/数据库公共工具
  export_pending.py           导出记忆库待译条目
  import_translations.py      译文写回记忆库
  apply_batch.py              调后台批量翻译接口回填内容表
  check_consistency.py        一致性体检（部分可自动修复）
  secret_scan.sh              提交前敏感信息扫描
references/
  schema.md                   表结构与字段约定
  pitfalls.md                 已知坑与排查方法
  patches.md                  站点侧代码补丁（isset 守卫等）
docs/
  leakage-review.md           开源前的敏感信息审查清单
```

## 快速开始

```bash
pip3 install pymysql
cp config.example.json config.json   # 填数据库与后台信息

# 1) 开「预先假翻译」，在后台把各内容表点一遍翻译（栏目表先翻）
# 2) 导出待译原文
python3 scripts/export_pending.py --out pending.json
# 3) 翻译后写回记忆库
python3 scripts/import_translations.py --in translations.json
# 4) 关「预先假翻译」，再点一次批量翻译（或用脚本）
python3 scripts/apply_batch.py --dry-run
python3 scripts/apply_batch.py
# 5) 体检
python3 scripts/check_consistency.py --fix
```

## 翻译规则（重要）

- 数字、型号（`M3X`、`ISO`、`CE`、`AHRI`）、邮箱、电话、URL **不翻译**；
- 品牌名 / 公司名按目标语言惯例翻译（`Co., Ltd.` → `GmbH` / `株式会社` / `주식회사` / `ش.م.م` 等），**不要音译**；
- HTML 只翻文本节点，标签与属性原样保留；
- 短 UI 文案（按钮、表单标签）机翻容易翻歪，建议 LLM 校对。

## 安全

- `config.json`、导出的 `pending*.json` / `translations*.json` 已在 `.gitignore` 中，**不要提交**；
- 提交前跑 `bash scripts/secret_scan.sh`；
- 详见 `docs/leakage-review.md`。

## License

MIT
