#!/usr/bin/env bash
# One-command setup for developers (for example, someone who has just forked or cloned the project).
#
# Run it from anywhere:   bash setup-dev.sh
#
# It will:
#   1. check that Python 3.10+, Node 18+ and npm are installed
#   2. create the Python virtual environment in ./venv (or reuse it)
#   3. install every Python package the site needs, plus the ones the tests need
#      (requirements-dev.txt, which includes requirements.txt)
#   4. copy config/config.example.json to config/config.json, unless that file already exists
#   5. install the JavaScript test tools exactly as locked, with `npm ci`
#
# It is safe to run again: it never overwrites your config.json or recreates an existing venv.
# Works in Git Bash on Windows, and on Linux and macOS.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

# --- 1. Prerequisites ---------------------------------------------------------------------------
step "Checking prerequisites"

for file in requirements-dev.txt package-lock.json config/config.example.json; do
  [ -f "$file" ] || fail "$file is missing. Run this script from the root of the project."
done

# The command for Python varies: python3 on Linux/macOS, python or "py -3" on Windows.
PYTHON=""
for candidate in python3 python "py -3"; do
  # $candidate is deliberately unquoted so that "py -3" splits into a command and its argument.
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PYTHON=$candidate
    break
  fi
done
[ -n "$PYTHON" ] || fail "Python 3.10 or newer is required (the bambulabs-api package needs it).
Install it from https://www.python.org/downloads/ and run this script again."

command -v node >/dev/null 2>&1 || fail "Node.js is required for the website tests, and was not found.
Install version 18 or newer from https://nodejs.org/ and run this script again."
command -v npm >/dev/null 2>&1 || fail "npm is required for the website tests, and was not found.
It normally comes with Node.js: https://nodejs.org/"
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
[ "$NODE_MAJOR" -ge 18 ] || fail "Node.js 18 or newer is required, but this is version $(node --version).
Update it from https://nodejs.org/ and run this script again."

echo "Python: $($PYTHON --version 2>&1)  Node: $(node --version)  npm: $(npm --version)"

# --- 2. Virtual environment ---------------------------------------------------------------------
step "Python virtual environment (venv)"

if [ -d venv ]; then
  echo "venv already exists; reusing it."
else
  $PYTHON -m venv venv || fail "Could not create the virtual environment.
On Debian, Ubuntu and Raspberry Pi OS, install the venv module first:  sudo apt install python3-venv"
  echo "Created venv."
fi

# Windows puts the interpreter in venv/Scripts, everything else in venv/bin.  Calling it directly
# means this script never has to "activate" the environment.
if [ -f venv/Scripts/python.exe ]; then
  VENV_PYTHON=venv/Scripts/python
  ACTIVATE="source venv/Scripts/activate"
elif [ -f venv/bin/python ]; then
  VENV_PYTHON=venv/bin/python
  ACTIVATE="source venv/bin/activate"
else
  fail "venv exists but has no Python in it. Delete the venv folder and run this script again."
fi

# --- 3. Python packages -------------------------------------------------------------------------
step "Python packages (site + tests)"
"$VENV_PYTHON" -m pip install -r requirements-dev.txt

# --- 4. Config ----------------------------------------------------------------------------------
step "Config file"
if [ -f config/config.json ]; then
  echo "config/config.json already exists; leaving it alone."
else
  cp config/config.example.json config/config.json
  echo "Created config/config.json from the example."
  CONFIG_CREATED=1
fi

# --- 5. JavaScript test tools -------------------------------------------------------------------
step "JavaScript packages (npm ci)"
npm ci

# --- Check it worked ----------------------------------------------------------------------------
step "Verifying"
"$VENV_PYTHON" -c "import bambulabs_api, pytest, pytest_benchmark; print('Python packages: OK')"
npx --no-install jest --version >/dev/null && echo "JavaScript packages: OK"

printf '\nAll set up.\n\nNext steps:\n'
printf '  1. Activate the virtual environment:   %s\n' "$ACTIVATE"
if [ "${CONFIG_CREATED:-0}" = "1" ]; then
  printf '  2. Edit config/config.json with your own printer details (it holds example values now).\n'
  printf '     It is ignored by git, so your access codes will not be committed.\n'
else
  printf '  2. Check config/config.json has your printer details.\n'
fi
printf '  3. Run the tests:                      pytest        (Python)\n'
printf '                                         npm test      (website)\n'
printf '     Performance tests, run on request:  pytest -m perf   and   npm run test:perf\n'
printf '  4. Run the site:                       python server/server.py\n'
