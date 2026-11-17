# 表结构与字段约定

> 表前缀以站点 `database.prefix` 为准（默认 `fa_`）。

## fa_multilingualcms_web — 站点语言

| 字段 | 说明 |
|---|---|
| id | 主键 |
| lang | **站点语言代码**，必须与 `fa_translate_lang.lang` 完全一致 |
| name | 语言名称（后台显示） |
| switch | 是否启用（1 启用） |
| en_name / country | 英文名 / 国家 |
| image | 国家图标，如 `/assets/country/pt.jpg` |
| indextpl | 首页模板 |

## fa_translate_lang — 语言字典

| 字段 | 说明 |
|---|---|
| id / name / pinyin / first | 字典主键与名称 |
| **lang** | **站点语言代码**（与 web.lang 对齐的那一列） |
| baidu / tencent / google / youdao / aliyun / volc / libretranslate / ai | 各翻译引擎的语言代码 |

记忆库与内容表用的是 **引擎代码**（`getFanyiLang()` 的返回值），
语言包翻译模块用的是 **站点语言代码**（`fanyi($text,'auto',$lang)` 直接传站点代码），
所以同一个词条在记忆库里可能有两套行，翻译时要认准 `from_lang`/`to_lang` 组合。

## fa_translate_memory — 翻译记忆库

| 字段 | 说明 |
|---|---|
| src_hash | `md5(规范化原文)`，规范化 = 去首尾空格 + 合并连续空白 |
| src_text | 原文 |
| from_lang | 源语言，内容翻译是主语言（如 en），语言包翻译是 `auto` |
| to_lang | 目标语言：内容翻译 = 引擎代码；语言包翻译 = 站点语言代码 |
| translated | 译文；**为空表示还没翻译**（预先假翻译写入的就是空） |
| use_translate | `fake` / `google` / `baidu` / `manual` …（命中时不看这一列） |
| hit_count | 命中次数 |
| md5 | 译文的 md5 |

唯一键：`(src_hash, from_lang, to_lang, use_translate)`。

## fa_fanyi_tables — 可翻译字段配置

| 字段 | 说明 |
|---|---|
| table_name | 表名（带前缀） |
| fanyi_fields | 逗号分隔的字段名，**字段必须真实存在于该表** |

## 内容表（news / cate / page / pro / standby / seokeyword / dbconfig / banner）

| 字段 | 说明 |
|---|---|
| lang | 行语言 |
| copy_id | 指向主语言行的 id（根行可为空） |
| cate_id | 指向**同语言**栏目行的 id（不是主语言栏目 id） |
| parent_id（cate 表） | 指向**同语言**父栏目的 id |
| fanyi_switch | 0 = 不翻译该行 |
| fanyi_sha1 | 源文指纹（sha1 of 拼接后的可翻译字段） |
| fanyi_num / fanyi_time | 翻译次数 / 最近翻译时间 |

## 栏目映射规则（重要）

```
目标栏目 = (lang = 目标语言 AND copy_id = 源栏目 id)
```
主语言栏目的 `copy_id` 通常为空，所以 `copy_id` 字段直接存主语言栏目的 id。

内容行的 `cate_id` 必须满足 `该 cate 行的 lang == 内容行的 lang`。

## 语言包（前台文案）

路径：`application/multilingualcms/lang/<语言>/index.php`，内容是 `<?php return [...]` 的键值对：

- **key** 是标识，**value 是英文原文**；
- 模板里 `{:lang('Company Name')}` 取的是 value 的翻译；
- 语言包文件由后台「多语言CMS → 语言包翻译」按主语言包 + 翻译记忆库生成。

## 相关插件目录

```
addons/translate/helper.php        翻译函数（translate_text / fanyi / getFanyiLang / get_google_lang）
addons/translate/library/LangCom.php   批量翻译主逻辑（fanyiOtherData / FanyiTableContent）
addons/multilingualcms/helper.php   栏目映射（getOtherLangCateId / getFanyiTablesFieldsArray）
addons/multilingualcms/controller/LangTranslation.php  语言包翻译
```
