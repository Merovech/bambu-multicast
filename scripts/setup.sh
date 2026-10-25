#!/bin/bash
# This script sets up a virtual environment for Python, activates
# it, then installs bambulabs-api.  It is required before running
# the server.

set -euo pipefail

python3 -m venv venv
source venv/bin/activate
pip install bambulabs-api==2.6.6
