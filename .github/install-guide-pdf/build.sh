#!/usr/bin/env bash
# Builds doc/install-guide.pdf from doc/install-guide.md, in GitHub's visual style.
#
#   Markdown --(pandoc, GitHub Flavored Markdown)--> HTML --(headless Chrome)--> PDF
#
# The styling is the github-markdown-css package (a pinned dev dependency, so run `npm ci` first);
# template.html next to this script wraps the page and adapts it for paper, and github-alerts.lua
# gives the Note/Tip/Important/Warning/Caution callouts GitHub's markup.  Chrome draws the page
# the way a browser does, which is what gives the GitHub look.
#
# Used by .github/workflows/install-guide-pdf.yml, and you can run it yourself:
#   bash .github/install-guide-pdf/build.sh
#
# Settings, all optional environment variables:
#   PANDOC        the pandoc command            (default: pandoc)
#   CHROME        the Chrome/Chromium command   (default: google-chrome)
#   CHROME_FLAGS  extra Chrome flags            (the workflow passes --no-sandbox)

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

PANDOC=${PANDOC:-pandoc}
CHROME=${CHROME:-google-chrome}

SOURCE=doc/install-guide.md
OUTPUT=doc/install-guide.pdf
CSS=node_modules/github-markdown-css/github-markdown.css
TEMPLATE=.github/install-guide-pdf/template.html
FILTER=.github/install-guide-pdf/github-alerts.lua

for file in "$SOURCE" "$CSS" "$TEMPLATE" "$FILTER"; do
  [ -f "$file" ] || { echo "ERROR: $file is missing." >&2
    [ "$file" = "$CSS" ] && echo "Run 'npm ci' first." >&2
    exit 1; }
done

# The first heading names the PDF in a viewer's title bar.
TITLE=$(grep -m1 -E '^# ' "$SOURCE" | sed -E 's/^# *//; s/<[^>]*>//g; s/^ +| +$//g')
[ -n "$TITLE" ] || TITLE="Install guide"

# Chrome decides how to show a file from its name, so the page needs a .html extension: without one
# it prints the HTML source as text.
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
HTML="$WORK/install-guide.html"

# --embed-resources puts the stylesheet inside the page, so the HTML is one self-contained file.
"$PANDOC" "$SOURCE" \
  --from=gfm --to=html5 --standalone \
  --template="$TEMPLATE" \
  --lua-filter="$FILTER" \
  --css="$CSS" --embed-resources \
  --metadata pagetitle="$TITLE" \
  --output "$HTML"

# Chrome wants a file:// URL and an absolute output path; under Git Bash on Windows both must be
# written Windows-style.
if command -v cygpath >/dev/null 2>&1; then
  URL="file:///$(cygpath -m "$HTML")"
  OUTPUT_ABS=$(cygpath -m "$PWD/$OUTPUT")
else
  URL="file://$HTML"
  OUTPUT_ABS="$PWD/$OUTPUT"
fi

rm -f "$OUTPUT"
# CHROME_FLAGS is deliberately unquoted so that several flags split into separate arguments.
# shellcheck disable=SC2086
"$CHROME" ${CHROME_FLAGS:-} --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUTPUT_ABS" "$URL" >/dev/null 2>&1 || true

# Chrome can exit quietly without producing anything, so check the result instead of its exit code.
if [ ! -s "$OUTPUT" ] || [ "$(head -c 4 "$OUTPUT")" != "%PDF" ]; then
  echo "ERROR: Chrome did not produce a PDF at $OUTPUT." >&2
  exit 1
fi

echo "Built $OUTPUT ($(wc -c < "$OUTPUT" | tr -d ' ') bytes) from $SOURCE."
