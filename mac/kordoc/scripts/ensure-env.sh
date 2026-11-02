#!/bin/bash
# macOS environment harness for the budget skills.
#  1. Finds Node.js (>=20) and Python (>=3.10) and RUNS a self-test on each.
#  2. Missing Node  -> downloads the pinned official tarball (SHA-256 checked) into engine/runtime.
#     Missing Python -> `brew install python` if Homebrew exists, else stops with instructions.
#  3. Installs kordoc from engine/package-lock.json (npm ci) if engine/node_modules is absent.
#  4. Raises kordoc's HWP section/record limits (scripts/patch-limits.cjs); --check-only only verifies.
#  5. Writes engine/env.json; exit 0 only when every test passes.
# Usage: ensure-env.sh [--check-only]
set -u
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$SKILL/engine"; RUNTIME="$ENGINE/runtime"
CHECK_ONLY=0; [ "${1:-}" = "--check-only" ] && CHECK_ONLY=1
NODE_VER=24.22.0
case "$(uname -m)" in
  arm64)  NODE_ARCH=arm64; NODE_SHA=6a9724d9b50a5f22b4816cded441b5a8d9ddae546191a5e5b7efa5a5e2ee26d5 ;;
  x86_64) NODE_ARCH=x64;   NODE_SHA=495e3f273c645f3c4677d438304cdfc701729ea5dec5728f5c8e76a2dece4b91 ;;
  *) echo "unsupported CPU: $(uname -m)" >&2; exit 1 ;;
esac
NODE_DIR="$RUNTIME/node-v$NODE_VER-darwin-$NODE_ARCH"
say() { echo "$@" >&2; }
die() { say "ERROR: $*"; exit 1; }

test_node() {  # $1 = node path
  [ -x "$1" ] || return 1
  local v; v="$("$1" --version 2>/dev/null)" || return 1
  [[ "$v" =~ ^v([0-9]+)\. ]] || return 1
  [ "${BASH_REMATCH[1]}" -ge 20 ] || return 1
  [ "$("$1" -e "const z=require('zlib');process.stdout.write(z.gunzipSync(z.gzipSync('ok')).toString())" 2>/dev/null)" = "ok" ] || return 1
  echo "$v"
}
test_python() {  # $1 = python path
  [ -x "$1" ] || return 1
  "$1" -c "import sys,sqlite3,json,zipfile,hashlib;assert sys.version_info>=(3,10);print('%d.%d.%d'%sys.version_info[:3])" 2>/dev/null
}

find_node() {
  local c v
  for c in "$(command -v node 2>/dev/null)" "$NODE_DIR/bin/node"; do
    [ -n "$c" ] && v="$(test_node "$c")" && { NODE="$c"; NODE_V="$v"; return 0; }
  done; return 1
}
find_python() {
  local c v
  for c in "$(command -v python3 2>/dev/null)" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    [ -n "$c" ] && v="$(test_python "$c")" && { PY="$c"; PY_V="$v"; return 0; }  # Xcode stub fails the test if CLT is absent
  done; return 1
}

if ! find_node; then
  say "Node.js (>=20) not found or failed self-test."
  [ $CHECK_ONLY = 1 ] && die "missing Node.js (--check-only)"
  mkdir -p "$RUNTIME" || die "cannot create $RUNTIME"
  TAR="$RUNTIME/node-v$NODE_VER-darwin-$NODE_ARCH.tar.gz"
  say "Downloading Node.js $NODE_VER"
  curl -fsSL --retry 2 -o "$TAR" "https://nodejs.org/dist/v$NODE_VER/node-v$NODE_VER-darwin-$NODE_ARCH.tar.gz" || die "download failed"
  GOT="$(shasum -a 256 "$TAR" | awk '{print $1}')"
  [ "$GOT" = "$NODE_SHA" ] || { rm -f "$TAR"; die "SHA-256 mismatch ($GOT). Nothing was installed."; }
  tar -xzf "$TAR" -C "$RUNTIME" && rm -f "$TAR"
  find_node || die "downloaded Node.js failed the self-test"
fi

if ! find_python; then
  say "Python (>=3.10) not found or failed self-test."
  [ $CHECK_ONLY = 1 ] && die "missing Python (--check-only)"
  if command -v brew >/dev/null 2>&1; then
    say "Installing Python with Homebrew"
    brew install python || die "brew install python failed"
    find_python || die "Python still failing the self-test after brew install"
  else
    die "Install Python 3.10+ (https://www.python.org/downloads/macos/ or Homebrew), then rerun."
  fi
fi

CLI="$ENGINE/node_modules/kordoc/dist/cli.js"
if [ ! -f "$CLI" ]; then
  say "Installing kordoc (npm ci)"
  [ $CHECK_ONLY = 1 ] && die "kordoc not installed (--check-only)"
  NPMDIR="$(dirname "$NODE")"
  (cd "$ENGINE" && PATH="$NPMDIR:$PATH" npm ci --omit=optional --omit=dev --ignore-scripts --no-audit --no-fund) || die "npm ci failed"
fi
KV="$(KORDOC_OFFLINE=1 "$NODE" "$CLI" --version 2>/dev/null)" || die "kordoc self-test failed"
[ "$KV" = "4.22.13" ] || die "unexpected kordoc version: $KV"
# kordoc 이 큰 HWP 의 뒤쪽 구역·레코드를 경고 없이 버리는 상한을 올린다(scripts/patch-limits.cjs 참고).
PATCH="$SKILL/scripts/patch-limits.cjs"; DIST="$ENGINE/node_modules/kordoc/dist"
if [ $CHECK_ONLY = 1 ]; then
  "$NODE" "$PATCH" "$DIST" --check || die "kordoc limits not raised; rerun without --check-only"
else
  "$NODE" "$PATCH" "$DIST" || die "kordoc limit patch failed"
fi

json() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
OUT=$(printf '{\n  "ok": true,\n  "node": "%s",\n  "node_version": "%s",\n  "python": "%s",\n  "python_args": [],\n  "python_version": "%s",\n  "kordoc_cli": "%s",\n  "kordoc_version": "%s",\n  "checked_utc": "%s"\n}\n' \
  "$(json "$NODE")" "$NODE_V" "$(json "$PY")" "$PY_V" "$(json "$CLI")" "$KV" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")
printf '%s' "$OUT" > "$ENGINE/env.json"
printf '%s' "$OUT"
exit 0
