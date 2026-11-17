#!/usr/bin/env bash
# 提交前敏感信息扫描：命中即阻断
#
# 可选：把本方特有的域名/IP/标识写进 .secrets.local（已被 .gitignore 忽略），
# 脚本会自动把它们当作额外的扫描模式。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

FAIL=0
scan() {
  local name="$1" pattern="$2"
  local hits
  hits=$(grep -rInE --exclude-dir=.git --exclude-dir=__pycache__ --exclude='secret_scan.sh' --exclude='.secrets.local' "$pattern" . 2>/dev/null | head -20)
  if [ -n "$hits" ]; then
    echo "[命中] $name"
    echo "$hits" | sed 's/^/    /'
    FAIL=1
  fi
}

echo "== 扫描密钥/凭据类内容"
scan "疑似密码赋值"      '(password|passwd|pwd|secret|access_key|secret_key|app_?secret)\s*[=:>]\s*["'"'"'][^"'"'"']{6,}'
scan "AK/SK 形态"       '\b(AKID[A-Za-z0-9]{10,}|AKLT[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16})\b'
scan "Basic 认证串"     'Basic [A-Za-z0-9+/=]{12,}'
scan "私钥"             'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY'
scan "数据库连接串"     'mysql://[^ <>]+:[^ <> @]+@'
scan "IP:端口 直连"     '\b(?!127\.0\.0\.1)\d{1,3}(\.\d{1,3}){3}:(21|80|443|2128|3306|888)\b'
scan "Cookie/Token 赋值" '(cookie|token|session)\s*[=:>]\s*["'"'"'][^"'"'"']{16,}'

echo "== 扫描站点/客户标识（需人工确认是否可公开）"
scan "内网/公网 IP"      '\b(?!127\.0\.0\.1|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)\d{1,3}(\.\d{1,3}){3}\b'

if [ -f .secrets.local ]; then
  echo "== 扫描 .secrets.local 中声明的本方标识"
  while IFS= read -r pat; do
    [ -z "$pat" ] && continue
    case "$pat" in \#*) continue;; esac
    scan "自定义: $pat" "$pat"
  done < .secrets.local
fi

echo
if [ "$FAIL" -eq 1 ]; then
  echo "结果：发现疑似敏感内容，请清理后再提交。"
  exit 1
fi
echo "结果：未发现明显的凭据类内容（站点标识类仍需人工确认）。"
