# 开源前的敏感信息审查清单

本技能涉及"给客户站点批量翻译 + 改数据"，非常容易把站点凭据和客户内容带进仓库。
**原则：仓库里只保留"方法"，不保留"任何具体站点的东西"。**

## 一、绝对不能进仓库（高危）

| 类别 | 例子 | 本仓库如何处理 |
|---|---|---|
| 数据库密码 | `db.password` | 只在 `config.json`（已 gitignore），示例文件里写占位符 |
| 后台登录密码 / Basic 认证 | `site.http_auth` | 同上 |
| 后台会话 Cookie | `fastadmin_sid=...`、`PHPSESSID=...` | 同上（属于临时凭据，泄露等于泄露后台） |
| FTP / SSH 账号密码 | 建站账号、面板账号 | 技能不包含任何部署脚本；若扩展需要，一律走环境变量 |
| 翻译服务 AK/SK | 百度 appid/secret、腾讯 SecretId/SecretKey、火山 AK/SK、有道 appid/secret | **示例配置里不出现**，只写"填你自己的" |
| 云厂商密钥 | AKID…、AKLT…、AKIA… | `scripts/secret_scan.sh` 扫描 |
| 站点授权码 / 许可证 | CMS 插件的站点标识文件、授权码 | 不收录 |
| 数据库连接串 | `mysql://<user>:<password>@<host>` | `secret_scan.sh` 扫描 |

## 二、不该进仓库（站点标识，可能牵涉客户）

| 类别 | 例子 |
|---|---|
| 客户域名 / 子域名 | 客户自己的站点域名、镜像站域名、翻译中转域名 |
| 服务器 IP / 端口 | 站点服务器 IP、数据库端口、面板端口 |
| 站点名称 / 公司名 | 站点配置里的公司名、品牌名、客户名 |
| 客户内容 | 栏目名、产品名、文案段落、新闻正文 |
| 客户联系信息 | 邮箱、电话、地址 |
| 站点唯一标识 | 授权文件里的 UUID |

> 这些信息在**私有运维记录**里可以留，但公开仓库里用 `example.com`、`your_db_user` 之类占位。

## 三、可以进仓库（方法本身）

- 表结构与字段语义（`references/schema.md`）——这些来自开源 CMS 本身；
- 通用规则：语言代码对齐规则、栏目映射规则、记忆库命中规则、翻译规则（数字/型号不译等）；
- 已知坑与排查方法（`references/pitfalls.md`）；
- 通用补丁（`references/patches.md`）——**只写改动逻辑，不带任何站点的文件名以外的上下文**，示例里用 `fa_multilingualcms_*` 通用前缀；
- 通用脚本（`scripts/*.py`），全部通过 `config.json` / 环境变量取连接信息。

## 四、提交前自检

```bash
bash scripts/secret_scan.sh
```

脚本会扫：密码类赋值、AKID/AKLT/AKIA 形态、Basic 认证串、私钥、数据库连接串、`IP:端口` 直连；
以及需要人工确认的站点标识类（IP、中文域名/站点名）。

另外人工确认：

- [ ] `git ls-files | xargs grep -nEi 'password|secret|token|cookie'` 没有真实值
- [ ] `config.json` 不在版本控制里（`git check-ignore config.json`）
- [ ] 导出的 `pending*.json` / `translations*.json`（含客户原文）不在版本控制里
- [ ] 提交历史里没有后来才删掉的凭据（`git log -p | grep -Ei 'password|secret'`）
- [ ] 截图/录屏/日志里没有后台地址、Cookie、AK/SK
- [ ] README 与文档里没有真实域名（用 example.com）

## 五、如果已经误提交

1. 立刻在服务商后台**轮换**所有相关凭据（密码、AK/SK、Basic 认证、Cookie 失效）；
2. `git filter-repo --path config.json --invert-paths` 或 BFG 清理历史；
3. 强制推送并通知协作者重新 clone；
4. 只删文件不改历史是不够的——凭据必须视为已泄露并轮换。

## 六、这个技能实际会碰到的"半敏感"东西

翻译流水线天然会接触**客户原文**（产品描述、公司介绍等）：

- 原文只存在运行机器的 `pending.json` / 记忆库里，属于**运行时数据**，不属于代码；
- 提交仓库前务必确认这些导出文件没被 `git add .` 带进去（`.gitignore` 已覆盖，但 `git add -f` 会绕过）；
- 如果要把译文样例放进文档，必须脱敏（换成 `Example Product` 之类）。
