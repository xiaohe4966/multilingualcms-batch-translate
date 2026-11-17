---
name: multilingualcms-batch-translate
description: 基于 FastAdmin 多语言CMS(MultilingualCMS)的批量翻译流水线：用"预先假翻译"模式把待译原文收进 fa_translate_memory，再用AI/翻译引擎补全译文并回填各内容表，最后复核并修复语言代码不一致、cate_id 跨语言串号、语言包词条缺失、表单必填校验缺失等问题。当用户提到多语言CMS批量翻译、fa_multilingualcms、fa_translate_memory、预先假翻译、假翻译、多语言站内容翻译、cate_id 串语言、语言包翻译时使用。
---

# 多语言CMS 批量翻译流水线（预先假翻译 → 补全记忆库 → 回填内容）

## 适用系统

FastAdmin 的 `MultilingualCMS`（Gitee: xiaohe4966/MultilingualCMS），核心表：

| 表 | 作用 |
|---|---|
| `fa_multilingualcms_web` | 站点语言列表（每个语言一行，`lang` 是站点语言代码） |
| `fa_multilingualcms_cate` | 栏目（`lang` + `copy_id` 指向主语言栏目 id） |
| `fa_multilingualcms_news/page/pro/standby/seokeyword/dbconfig` | 各内容表（`lang` + `copy_id` 指向主语言行 id） |
| `fa_multilingualcms_fanyi_tables` | 实际叫 `fa_fanyi_tables`：`table_name` → `fanyi_fields`（要翻译的字段） |
| `fa_translate_memory` | 翻译记忆库：`src_hash/src_text/from_lang/to_lang/translated/use_translate` |
| `fa_translate_lang` | 语言字典：`lang` 是站点代码，`baidu/tencent/google/...` 各引擎代码 |

> 表名前缀以站点配置为准（`application/database.php` / `.env` 里的 `prefix`）。

## 核心原理

站点自带的批量翻译按 `fanyi_tables.fanyi_fields` 逐字段调用翻译函数，翻译结果写回目标语言行，并留下 `fanyi_sha1`（源文指纹）用于判断是否需要重译。

**"预先假翻译"（pre_fake_translate）** 开关打开后，翻译函数不会真的调翻译接口，而是：
1. 把原文写进 `fa_translate_memory`（`use_translate='fake'`、`translated=''`）；
2. 在内容行里写入 `待翻译 <原文>` 占位（末尾带零宽字符，保证源文指纹变化、触发后续重译）。

于是形成流水线：

```
① 开启预先假翻译 → 后台批量翻译 → 原文进记忆库，内容写占位
② 导出记忆库待译条目 → AI/翻译引擎翻译 → 写回 memory.translated
③ 关闭预先假翻译 → 再点一次批量翻译 → 命中记忆库，内容被真实译文覆盖
④ 一致性复核（语言代码/cate_id/字段配置/语言包/必填校验）
```

记忆库命中条件是 `src_hash=md5(规范化原文)` 且 `translated<>''`，**与 use_translate 无关**，所以第③步不需要改 use_translate。

## 前置条件

- MySQL 可访问（`3306` 对外开放；若只允许服务器本机连接，需自行在服务器上执行等价 SQL）。
- 后台管理员可登录（拿得到 `fastadmin_sid` / `PHPSESSID`），用于第 4 步调用后台批量翻译接口。
- `pip3 install pymysql`

## 工作流程

### 第 0 步：配置

复制 `config.example.json` 为 `config.json`（**已被 .gitignore 忽略，禁止提交**），填入数据库与站点信息：

```bash
cp config.example.json config.json
```

### 第 1 步：开启"预先假翻译"并收集原文

后台 → 插件 → translate → 配置 → `pre_fake_translate` 设为「是」；
然后逐个内容表点「翻译」（栏目表 `cate` 要**先**翻，见坑位 #4）。

### 第 2 步：导出待译条目

```bash
python3 scripts/export_pending.py --out pending.json
```

输出 `[{"to_lang":"de","src_text":"...","from_lang":"en","id":123}, ...]`，按目标语言分组。

### 第 3 步：翻译并回填记忆库

翻译要求（**必须遵守**）：
- 数字、型号（如 M3X、ISO、CE、AHRI）、邮箱、电话、URL、品牌名/公司名**保持原样不译**；
- 品牌名按目标语言惯例处理（有限公司→GmbH/株式会社/주식회사/ش.م.م 等），**不要把公司名音译**；
- HTML 内容只翻文本节点，标签与属性原样保留；
- 短 UI 文案（表单标签、按钮）机器翻译常常翻歪，这部分建议由 LLM 人工校对。

写回：

```bash
python3 scripts/import_translations.py --in translations.json
```

`translations.json` 格式：`[{"src_text":"...","to_lang":"de","from_lang":"en","translated":"..."}]`。

### 第 4 步：回填内容表

关掉 `pre_fake_translate`，再在后台逐表点一次「翻译」即可（记忆库命中直接用真实译文）。
也可脚本化：

```bash
python3 scripts/apply_batch.py --dry-run     # 先看会翻哪些表
python3 scripts/apply_batch.py                # 实际调用后台批量翻译接口
```

### 第 5 步：一致性与残留复核

```bash
python3 scripts/check_consistency.py            # 只报告
python3 scripts/check_consistency.py --fix      # 修复可自动修的项
```

覆盖：站点语言代码与语言字典不一致、`fanyi_fields` 指向不存在的列、`cate_id`/`parent_id` 跨语言串号、内容里残留 `待翻译` 占位、语言包词条缺失。

## 已知坑（务必先读 references/pitfalls.md）

1. **站点语言代码必须等于语言字典的 `lang`**：`fa_multilingualcms_web.lang` 要与 `fa_translate_lang.lang` 完全一致（如 `ko/fr/es`，不是百度代码 `kor/fra/spa`），否则批量翻译报「找不到 xx 对应的语言配置」。
2. **`fanyi_fields` 里的字段必须真实存在于该表**，否则 PHP 7.4 下 notice 被转成 ErrorException，整批 500。
3. **HTML 字段分支没有 isset 守卫**会因不存在的字段直接 500，补丁见 `references/patches.md`。
4. **栏目表要先翻**：目标语言的栏目没生成时，内容行的 `cate_id` 会串到主语言栏目（见坑 #5）。
5. **`getOtherLangCateId()` 的兜底会把主语言栏目 id 写进其它语言行**——这是 `cate_id` 串号的根因，补丁见 `references/patches.md`。
6. **翻译通道**：免费谷歌中转（`fanyi.<域名>/translate`）并发一高就被 Google 429；腾讯 TMT 免费额度常已用尽；火山(Volc)/百度/有道需要站点配置里已有 AK/SK。语言代码别名（如 `kor→ko`、`fra→fr`、`vie→vi`）要在 `get_google_lang()` 里补上，否则会原样返回英文。
7. **查询缓存 600s**：改了记忆库后立刻重跑，可能命中旧缓存；必要时清 `runtime/cache`。
8. **手改语言包**：语言包在 `application/multilingualcms/lang/<语言>/index.php`，值是**英文原文**（模板里的 `lang('xxx')` 取的是 value）；补新词条要先加到 `en/index.php`，再重生成各语言。

## 开源前的敏感信息检查

见 `docs/leakage-review.md`。**任何站点凭据、AK/SK、域名 IP、客户内容都不允许进仓库**；提交前跑：

```bash
bash scripts/secret_scan.sh
```
