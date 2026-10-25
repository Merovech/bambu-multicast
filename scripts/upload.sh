#!/usr/bin/env bash
# Uploads only what the Pi needs to run the site.  Run it from anywhere:
#
#   bash scripts/upload.sh user@server   upload, and show what was sent and what arrived
#   bash scripts/upload.sh --list        just list the files that would be uploaded (nothing is sent)
#
# user@server is your login on the Pi and its name or address, for example pi@raspberrypi.local or
# me@192.168.1.60.  A host name from your ~/.ssh/config works too.
#
# Uploaded:   the server's Python files, the website's files, your config/config.json, and scripts/setup.sh.
# Not uploaded: tests, docs, node_modules, package files, __pycache__, config.example.json, and the
# venv.  The venv is deliberately left out: the one on this PC contains Windows programs and paths and
# cannot run on the Pi.  The Pi keeps its own venv (made by scripts/setup.sh); this script never touches it.
#
# To use different ssh settings, such as a key file, set UPLOAD_SSH, for example:
#   UPLOAD_SSH="ssh -i ~/.ssh/pi_key" bash scripts/upload.sh pi@raspberrypi.local
#
# Files are sent as one tar stream over a single ssh connection, so you are asked for a password (if
# you use one) only once, and the folders are created on the Pi if they don't exist.  The Pi reports
# back every file it unpacked, and this script checks that list against what it sent.  Files you have
# deleted here are NOT deleted on the Pi.

set -euo pipefail

SELF=${BASH_SOURCE[0]}
cd "$(dirname "$SELF")/.."

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

HOST=
LIST_ONLY=no
for arg in "$@"; do
  case $arg in
    --list) LIST_ONLY=yes ;;
    -h|--help)
      awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$SELF"
      exit 0
      ;;
    -*) fail "Unknown option '$arg'. Run with --help to see how to use this script." ;;
    *)
      [ -z "$HOST" ] || fail "Give only one user@server (you gave '$HOST' and '$arg')."
      HOST=$arg
      ;;
  esac
done

if [ "$LIST_ONLY" = no ] && [ -z "$HOST" ]; then
  fail "Say where to upload to, as user@server. For example:
  bash scripts/upload.sh pi@raspberrypi.local"
fi
# Letters, digits, dots, dashes and underscores only, and never a leading dash, so that whatever is typed
# here can only ever be read by ssh as a place to connect to, and not as one of its options.
if [ -n "$HOST" ] && ! [[ $HOST =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*(@[A-Za-z0-9][A-Za-z0-9._-]*)?$ ]]; then
  fail "'$HOST' doesn't look like user@server. Use letters, digits, dots and dashes only, like pi@raspberrypi.local."
fi

REMOTE_DIR=printer-page     # relative to your home folder on the Pi
SSH=${UPLOAD_SSH:-ssh}

# Keep this list in step with server/server.py: its imports, and STATIC_FILES for the website.
# (tests/server/test_upload_script.py checks that it is.)
FILES=(
  server/server.py
  server/config.py
  server/print_errors.py
  server/print_errors.json
  server/print_result.py
  server/printer_status_map.py

  client/index.html
  client/app.js
  client/styles.css
  client/tailwind.css

  config/config.json

  scripts/setup.sh
)

for file in "${FILES[@]}"; do
  [ -f "$file" ] || { echo "ERROR: $file is missing." >&2
    case "$file" in
      client/tailwind.css) echo "Build it with: npm run build:css" >&2 ;;
      config/config.json)  echo "Create it from config/config.example.json." >&2 ;;
    esac
    exit 1; }
done

if [ "$LIST_ONLY" = yes ]; then
  printf '%s\n' "${FILES[@]}"
  exit 0
fi

# 8234 -> "8.0 KB"
human() { awk -v b="$1" 'BEGIN { if (b < 1024) printf "%d B", b; else printf "%.1f KB", b / 1024 }'; }

# --- What is about to be sent ------------------------------------------------------------------
TOTAL=0
echo "Uploading to $HOST, into ~/$REMOTE_DIR/"
echo
printf '  %-32s %10s\n' "FILE" "SIZE"
for file in "${FILES[@]}"; do
  size=$(wc -c < "$file" | tr -d ' ')
  TOTAL=$((TOTAL + size))
  printf '  %-32s %10s\n' "$file" "$(human "$size")"
done
printf '  %-32s %10s\n' "$(printf '%.0s-' {1..32})" "----------"
printf '  %-32s %10s\n' "${#FILES[@]} files" "$(human "$TOTAL")"
echo

# Stage the files in a temporary folder, so that only the listed files can ever be sent and so that
# shell scripts can be given Unix line endings.  (On Windows, git may have checked them out with
# Windows line endings, which make bash on the Pi fail with "$'\r': command not found".)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
for file in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$file")"
  cp "$file" "$STAGE/$file"
  case "$file" in *.sh) sed -i 's/\r$//' "$STAGE/$file" ;; esac
done

# --- Send --------------------------------------------------------------------------------------
echo "Sending..."
SECONDS=0
# The Pi prints "DEST <full path>" first, then each file it unpacks (tar -v).  stderr is included so
# that any problem tar reports is shown below instead of being lost.
REMOTE_CMD="mkdir -p ~/$REMOTE_DIR && cd ~/$REMOTE_DIR && echo \"DEST \$(pwd)\" && tar --no-same-owner -xvf - 2>&1"
# $SSH is deliberately unquoted so that "ssh -i key" splits into a command and its options.
# shellcheck disable=SC2086
if ! REPLY=$(tar -cf - -C "$STAGE" . | $SSH "$HOST" "$REMOTE_CMD"); then
  echo >&2
  echo "ERROR: the upload failed.  What the Pi said:" >&2
  echo "$REPLY" | sed 's/^/  /' >&2
  exit 1
fi

# --- What arrived ------------------------------------------------------------------------------
DEST=""
RECEIVED=()
while IFS= read -r line; do
  line=${line%$'\r'}
  case "$line" in
    "DEST "*) DEST=${line#DEST } ;;
    ""|*/)    ;;                       # blank lines and folder entries
    *)        RECEIVED+=("${line#./}") ;;
  esac
done <<< "$REPLY"

echo
echo "Arrived on the Pi, in ${DEST:-~/$REMOTE_DIR}:"
for file in "${RECEIVED[@]}"; do
  printf '  %s\n' "$file"
done

MISSING=()
for file in "${FILES[@]}"; do
  printf '%s\n' "${RECEIVED[@]}" | grep -qxF "$file" || MISSING+=("$file")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
  echo >&2
  echo "WARNING: these files were sent but the Pi did not report unpacking them:" >&2
  printf '  %s\n' "${MISSING[@]}" >&2
  exit 1
fi

echo
echo "Done: ${#RECEIVED[@]} files ($(human "$TOTAL")) uploaded to $HOST:${DEST:-~/$REMOTE_DIR} in ${SECONDS}s."
echo "Not touched on the Pi: its venv, and any files you have deleted here."
echo "If server/ files changed, restart the service on the Pi; client/ files need no restart."
