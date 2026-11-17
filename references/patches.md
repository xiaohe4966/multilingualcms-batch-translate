# 站点侧代码补丁

> 这些是 CMS 站点侧的健壮性修复，**先 review 再手工应用**（不同版本行号可能不同）。
> 通用做法：改前先备份 `文件名.bak_YYYYMMDD`。

## 补丁 1：HTML 字段分支加 isset 守卫

文件：`addons/translate/library/LangCom.php`，函数 `FanyiTableContent()`

问题：`fanyi_fields` 里配了表里不存在的列时，非 HTML 分支有 `isset` 判断，
HTML 分支（`_content` 结尾）没有 → PHP 7.4 下 notice 被转成 ErrorException → 整批 500。

```php
             if (in_array($field, $htmlFieldArr) || preg_match('/_content$/', $field)) {
+                if (!isset($cateNew[$field])) {
+                    continue;  // 字段在本表中不存在时跳过，避免整批翻译中断
+                }
                 if (strlen($cateNew[$field]) > 0) {
```

## 补丁 2：`getOtherLangCateId()` 不再回退到主语言栏目

文件：`addons/multilingualcms/helper.php`

问题：目标语言栏目不存在时兜底返回主语言栏目的 id → 内容行 `cate_id` 串语言。

```php
             if (!$OtherLangCateId) {
-                $OtherLangCateId = Db::name('multilingualcms_cate')
-                    ->where('id', $cate['id'])
-                    // ->where('lang', $lang)
-                    ->value('id');
-            }
-
-            if (!$OtherLangCateId) {
-                var_dump('getOtherLangCateId 没有找到', $cate_id, $lang);
-                exit;
+                //目标语言还没有对应栏目时不能回退到主语言栏目，否则内容行会指向别的语言的栏目
+                throw new \Exception('未找到语言 ' . $lang . ' 对应的栏目(源栏目id=' . $cate_id . ')，请先翻译栏目');
             }
 
             return $OtherLangCateId;
         } else {
-            var_dump('getOtherLangCateId 没有找到', $cate_id, $lang);
-            exit('getOtherLangCateId 没有找到主语言该分类');
-            throw new \Exception('未找到主语言该分类');
+            throw new \Exception('getOtherLangCateId 未找到主语言该分类: ' . $cate_id);
         }
```

调用方 `LangCom::fanyiOtherDataItem()` 已用 `try/catch (\Throwable)` 包住，会跳过该行，不会写脏数据。

## 补丁 3：翻译通道语言代码别名

文件：`addons/translate/helper.php`，函数 `get_google_lang()` 的 `$lang_map`

问题：中转只认谷歌语言代码，遇到百度码会**原样返回英文**（看起来翻译成功其实没翻）。

```php
             'ko' => 'ko',// 韩语
+            'kor' => 'ko',// 韩语(百度语言代码)
             'de' => 'de',// 德语
             'fr' => 'fr',// 法语
+            'fra' => 'fr',// 法语(百度语言代码)
             'fin' => 'fi',// 德语
             'dan' => 'da',// 德语
             'cht' => 'zh-TW',// 台湾繁体
             'spa' => 'es',// 德语
+            'vie' => 'vi',// 越南语(百度语言代码)
             'ar' => 'ar',// 阿拉伯语
             'ara' => 'ar',// 阿拉伯语
```

## 补丁 4：`getFanyiLang()` 引擎没配语言代码时退回其它引擎

文件：`addons/translate/helper.php`，函数 `getFanyiLang()`

问题：字典里 `google/youdao/aliyun/libretranslate` 等列对多数语言是空的，
切换到这些引擎时会直接抛异常。

```php
             $engineCols = ['baidu','tencent','google','youdao','aliyun','volc','libretranslate','ai'];
             $row = \think\Db::name('translate_lang')->where('lang', $lang)->cache(120)->find();
+            if (!$row && in_array($use_translate, $engineCols, true)) {
+                //站点语言代码与语言字典不一致时，用翻译引擎的语言代码反查
+                $row = \think\Db::name('translate_lang')->where($use_translate, $lang)->cache(120)->find();
+            }
             if (!$row) { ...抛异常... }
-            $fanyi_lang = $row[$use_translate] ?? '';
+            $fanyi_lang = !empty($row[$use_translate]) ? trim((string)$row[$use_translate]) : '';
+            if ($fanyi_lang === '') {
+                //当前引擎没配这个语言代码时，退回其它引擎已配置的语言代码
+                foreach ($engineCols as $col) {
+                    if (!empty($row[$col])) { $fanyi_lang = trim((string)$row[$col]); break; }
+                }
+            }
+            if ($fanyi_lang === '') { $fanyi_lang = $lang; }
```

## 补丁 5：前台表单必填校验

模板（例：`application/multilingualcms/view/index/public/footer.html`）

```html
-            <input type="text" id="companyName" name="company" placeholder="..." autocomplete="off">
+            <input type="text" id="companyName" name="company" placeholder="..." autocomplete="off" required>
```
公司名、联系人、电话、邮箱、验证码都要加 `required`（页脚另一个表单记得补验证码）。

后台（例：`application/multilingualcms/controller/Gbook.php` 的 `add()`）

```php
             $data = $this->request->param();
+            // 必填项校验（公司名称、联系人、电话、邮箱）
+            $langArr = [];
+            try {
+                $curLang = getDomainLang();
+                $langFile = ROOT_PATH . 'application' . DS . 'multilingualcms' . DS . 'lang' . DS . $curLang . DS . 'index.php';
+                if (is_file($langFile)) { $langArr = (array)include $langFile; }
+            } catch (\Throwable $th) {}
+            $requiredFields = ['company' => 'Company', 'name' => 'Contact Person', 'tel' => 'Phone Number', 'email' => 'Email'];
+            $missingFields  = [];
+            foreach ($requiredFields as $field => $label) {
+                if (trim((string)($data[$field] ?? '')) === '') { $missingFields[] = $langArr[$label] ?? $label; }
+            }
+            if ($missingFields) {
+                $this->error(($langArr['Please fill in the required fields'] ?? 'Please fill in the required fields') . ': ' . implode(', ', $missingFields));
+            }
```

（语言包里的 `Company` / `Contact Person` / `Phone Number` / `Email` / `Please fill in the required fields`
需要先在主语言包补上并重新生成各语言语言包。）

## 补丁 6：表单标签拼接改单个词条

```html
-            <label>{:lang('Company')} {:lang('xingming')}<span class="required-star">*</span></label>
+            <label>{:lang('Company Name')}<span class="required-star">*</span></label>
```
`Company` + `Name` 拼接在非英语里语序不对（"الشركة الاسم"），改用单个 `Company Name` 词条。
