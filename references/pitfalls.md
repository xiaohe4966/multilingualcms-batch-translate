# 已知坑与排查方法

## 1. 站点语言代码必须等于语言字典的 `lang`

**现象**：批量翻译报 `getFanyiLang:xx找不到baidu对应的语言配置`（整批 500）。

**原因**：`fa_multilingualcms_web.lang` 里写了**翻译引擎的语言代码**（百度码 `kor/fra/spa/ara`），
而 `fa_translate_lang.lang` 存的是站点代码（`ko/fr/es/ar`），查不到。

**排查**：
```sql
SELECT w.id, w.lang, w.name FROM fa_multilingualcms_web w
LEFT JOIN fa_translate_lang t ON t.lang = w.lang
WHERE w.lang <> '' AND t.lang IS NULL;
```
修法：把 web.lang 改成字典里的代码；引擎代码在字典的 `baidu/tencent/google` 等列。

## 2. `fanyi_fields` 里的字段必须真实存在

**现象**：`ErrorException ... 未定义数组索引: xxx` 整批 500。

**原因**：语言包/字段配置里写了表里没有的列（例如把别的表的 `xxx_content` 配给了 cate）。
`LangCom::FanyiTableContent()` 里 HTML 字段分支（`_content` 结尾）直接取 `$cateNew[$field]`，
非 HTML 分支才有 `isset` 判断。PHP 7.4 下 notice 会被 ThinkPHP 转成 ErrorException。

**排查**：
```sql
SELECT id, table_name, fanyi_fields FROM fa_fanyi_tables;
```
逐表比对 `information_schema.columns`。修法：改配置（去掉不存在的列）+ 给代码加守卫（见 patches.md）。

## 3. `cate_id` 跨语言串号

**现象**：某语言的产品/新闻在前台不显示、或归到别的语言的栏目下。

**原因**：`getOtherLangCateId()` 在"目标语言的栏目还不存在"时会**兜底返回主语言栏目的 id**，
于是内容行指向了英文栏目。

**为什么栏目会"还不存在"**：批量翻译是按表顺序做的，栏目表（cate）排在内容表后面时，
内容表先翻 → 目标语言的栏目还没生成 → 全部走兜底。

**修法**：
1. 先翻栏目表再翻内容表；
2. 用 `scripts/check_consistency.py --fix` 修数据；
3. 去掉代码里的兜底（见 patches.md），让找不到栏目时跳过该行而不是写错 id。

## 4. `parent_id` 也会串语言

栏目行的 `parent_id` 必须指向同语言的父栏目。翻译时用 `getLangParentId()` 映射，
映射不到时会留下主语言的 id。`check_consistency.py --fix` 同样能修。

## 5. 翻译通道与限流

| 通道 | 说明 |
|---|---|
| 免费谷歌中转（自建 `fanyi.<域名>/translate`） | 无需 key，但并发一高会被 Google 429（返回「sending automated queries」） |
| 腾讯云 TMT | 免费额度通常已用尽，报 `service free amount of this month has been used up` |
| 火山 Volc | 需 AK/SK，站点配置里有，QPS 10，质量较好 |
| 百度 | 需 appid/secret，QPS 1，质量较好 |
| 有道 | 需 appid/secret，短句质量偏差 |

**语言代码别名**：中转只认谷歌代码，`kor/fra/spa/ara/vie` 都不认识，会**原样返回英文**（看起来"翻译成功"其实是没翻）。
要在 `get_google_lang()` 里补别名：`kor→ko`、`fra→fr`、`spa→es`、`ara→ar`、`vie→vi`。

## 6. 查询缓存 600 秒

`translate_text()` 对记忆库的查询带 `->cache(600)`，命中的是旧结果。
刚写完记忆库就重跑批量翻译，可能仍然取到"未命中"的结果。
遇到这种情况清 `runtime/cache` 或等 10 分钟。

## 7. 语言包词条缺失

**现象**：某语言页面上某个文案还是英文（例如表单标题没翻译）。

**原因**：模板 `{:lang('Inquiry Form')}` 用了语言包里没有的 key。
语言包是"主语言包 + 记忆库"生成的，**key 缺失 → 所有语言都显示英文原文**。

**排查**：把模板里所有 `lang('...')` 的 key 抽出来，和主语言包的 key 比对（`check_consistency.py --lang-dir ... --view-dir ...`）。
修法：先在主语言包补英文，再重新生成各语言语言包。

## 8. 语言包的值是英文原文

语言包里 `key => 英文原文`，
翻译记忆库里存的是**值**（英文原文）的 hash。
所以补译文时要按**英文原文**去匹配记忆库，不是按 key。

## 9. 短 UI 文案机翻容易翻歪

`Submit` 会被翻成"提供/存入"，`Home` 会被翻成"房子"，`Links` 被翻成"连接"。
表单标签、按钮、导航这类短词建议由 LLM 校对后写回记忆库。

## 10. 必填项

前台表单若没有 `required` 属性，浏览器不会拦截空提交；
后台 `gbook/add` 也要自己校验必填，否则空留言会入库。
见 patches.md 的表单校验补丁。

## 11. 翻译记忆库命中与 `use_translate` 无关

记忆库查询不带 `use_translate` 条件，只要 `translated <> ''` 就算命中。
所以外部工具补全译文后，**不需要**改 `use_translate`，关掉"预先假翻译"重跑一次即可回填。
