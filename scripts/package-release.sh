#!/usr/bin/env bash
# Builds the release zip for end users: build/bambu-multicast-<version>.zip
#
#   bash scripts/package-release.sh 1.0.0                 version given on the command line
#   bash scripts/package-release.sh                       version taken from the git tag on HEAD (v1.0.0 -> 1.0.0)
#   bash scripts/package-release.sh --ref v1.0.0 1.0.0    package an older commit or tag instead of HEAD
#   bash scripts/package-release.sh --out /tmp/zips 1.0.0 put the zip somewhere other than build/
#   bash scripts/package-release.sh --allow-dirty 1.0.0   package HEAD even though tracked files have uncommitted changes
#
# A version looks like 1.0.0 or 1.0.0-rc1.  Everything goes inside one folder, bambu-multicast-<version>/.
#
# The zip is made with `git archive`, so only COMMITTED files go in, and the export-ignore lines in
# .gitattributes decide what is left out (tests, developer scripts, package files and so on).  Nothing is copied
# from your working folder.  After building, the script checks the zip's contents and deletes the zip
# if something is missing or something that must not ship is in it.
#
# Needs git, and either unzip or Python to read the zip back.  It does not run the tests.

set -euo pipefail

fail() {
  echo "Error: $*" >&2
  exit 1
}

REF=HEAD
OUT=
VERSION=
ALLOW_DIRTY=no

while [ $# -gt 0 ]; do
  case $1 in
    --ref)
      [ $# -ge 2 ] || fail "--ref needs a commit, branch or tag after it."
      REF=$2
      shift 2
      ;;
    --out)
      [ $# -ge 2 ] || fail "--out needs a folder after it."
      OUT=$2
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY=yes
      shift
      ;;
    -h|--help)
      sed -n '2,17p' "$0"
      exit 0
      ;;
    -*)
      fail "Unknown option '$1'. Run with --help to see the options."
      ;;
    *)
      [ -z "$VERSION" ] || fail "Give only one version (you gave '$VERSION' and '$1')."
      VERSION=$1
      shift
      ;;
  esac
done

case $REF in
  -*) fail "'$REF' is not a commit, branch or tag." ;;
esac

# A relative --out is relative to where you ran the script, not to the project folder.
if [ -n "$OUT" ]; then
  case $OUT in
    /*|[A-Za-z]:*) ;;
    *) OUT=$PWD/$OUT ;;
  esac
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -n "$OUT" ] || OUT=$PWD/build

command -v git >/dev/null 2>&1 || fail "git is not installed, and the release zip is made with git."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "This folder is not a git repository, so there is nothing to package. Run the script from a clone of the project."
[ -z "$(git rev-parse --show-cdup)" ] || fail "The project folder is not the top of a git repository."

git rev-parse --verify --quiet "$REF^{commit}" >/dev/null \
  || fail "'$REF' is not a commit, branch or tag in this repository."

if [ -z "$VERSION" ]; then
  TAG=$(git describe --tags --exact-match "$REF" 2>/dev/null || true)
  VERSION=${TAG#v}
  [ -n "$VERSION" ] || fail "No version given, and $REF has no git tag to take it from.
Give one, for example:  bash scripts/package-release.sh 1.0.0
(or tag the release first, for example:  git tag v1.0.0)"
fi

if ! [[ $VERSION =~ ^[0-9]+(\.[0-9]+)*(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$ ]]; then
  fail "'$VERSION' is not a valid version. Use digits and dots, optionally followed by a dash and a suffix, like 1.0.0 or 1.0.0-rc1."
fi

if [ "$ALLOW_DIRTY" = no ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Error: some files you track have changes that are not committed:" >&2
  git status --short --untracked-files=no >&2
  fail "The zip is built from what is committed, so those changes would be missing from it.
Commit them first, or run again with --allow-dirty if leaving them out is what you want."
fi

git cat-file -e "$REF:client/tailwind.css" 2>/dev/null \
  || fail "client/tailwind.css is not committed in $REF. Run 'npm run build:css', commit client/tailwind.css, and try again."

PREFIX=bambu-multicast-$VERSION
ZIP=$OUT/$PREFIX.zip
mkdir -p "$OUT"
git archive --format=zip --prefix="$PREFIX/" -o "$ZIP" "$REF"

list_zip() {
  local python
  if command -v unzip >/dev/null 2>&1; then
    unzip -Z1 "$ZIP"
    return
  fi
  for python in python3 python; do
    if "$python" -c '' >/dev/null 2>&1; then
      "$python" -c 'import sys, zipfile; print("\n".join(zipfile.ZipFile(sys.argv[1]).namelist()))' "$ZIP"
      return
    fi
  done
  echo "Neither unzip nor Python is installed, so the zip cannot be checked." >&2
  return 1
}

REQUIRED=(
  server/server.py server/config.py server/print_errors.py server/print_errors.json
  server/print_result.py server/printer_status_map.py
  client/index.html client/app.js client/styles.css client/tailwind.css
  config/config.example.json scripts/setup.sh requirements.txt LICENSE THIRD_PARTY_NOTICES.md
  doc/install-guide.md
)
FORBIDDEN_FILES=(
  package.json package-lock.json pytest.ini requirements-dev.txt setup-dev.sh
  scripts/setup-dev.sh scripts/upload.sh scripts/venv.sh scripts/package-release.sh
  tailwind.config.js tailwind.input.css .gitattributes .gitignore
  config/config.json doc/future-to-do-list.md doc/release-checklist.md
)
FORBIDDEN_FOLDERS=(tests .github node_modules build .claude)

if ! LISTING=$(list_zip | tr -d '\r') || [ -z "$LISTING" ]; then
  rm -f "$ZIP"
  fail "Could not read back $ZIP to check it, so it was deleted."
fi

PROBLEMS=()
FILE_COUNT=0
while IFS= read -r entry; do
  case $entry in
    */) ;;
    *) FILE_COUNT=$((FILE_COUNT + 1)) ;;
  esac
  if [ "$entry" = "$PREFIX/" ]; then
    continue
  fi
  case $entry in
    "$PREFIX"/*) ;;
    *) PROBLEMS+=("'$entry' is not inside the $PREFIX/ folder"); continue ;;
  esac
  rel=${entry#"$PREFIX/"}
  case $rel in
    __pycache__/*|*/__pycache__/*|*.pyc) PROBLEMS+=("'$rel' is Python cache that must not ship") ;;
  esac
  for name in "${FORBIDDEN_FILES[@]}"; do
    [ "$rel" != "$name" ] || PROBLEMS+=("'$rel' must not be in the release")
  done
  for name in "${FORBIDDEN_FOLDERS[@]}"; do
    case $rel in
      "$name"|"$name"/*) PROBLEMS+=("'$rel' must not be in the release") ;;
    esac
  done
done <<< "$LISTING"

for name in "${REQUIRED[@]}"; do
  grep -Fxq -- "$PREFIX/$name" <<< "$LISTING" || PROBLEMS+=("'$name' is missing")
done

if [ ${#PROBLEMS[@]} -gt 0 ]; then
  rm -f "$ZIP"
  echo "The release zip is wrong, so it was deleted:" >&2
  printf '  - %s\n' "${PROBLEMS[@]}" >&2
  fail "Fix the problems above (usually .gitattributes, or a file that is not committed) and run again."
fi

BYTES=$(wc -c < "$ZIP" | tr -d ' ')
if command -v sha256sum >/dev/null 2>&1; then
  SHA=$(sha256sum < "$ZIP" | cut -d ' ' -f 1)
else
  SHA=$(shasum -a 256 < "$ZIP" | cut -d ' ' -f 1)
fi

echo "Release zip checked and ready:"
echo "  File:    $ZIP"
echo "  Size:    $BYTES bytes ($((BYTES / 1024)) KB)"
echo "  Files:   $FILE_COUNT"
echo "  SHA-256: $SHA"
echo
echo "Still to do by hand (this script cannot check them):"
echo "  - Run 'pytest' and 'npm test' and make sure both pass."
echo "  - Unzip this file, open the site once in a browser, and confirm it is styled,"
echo "    the cameras load and nothing is blocked in the browser console."
