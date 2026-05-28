#!/usr/bin/env bash
# Render build script — runs on every deploy.
# Fails the build immediately on any error.

set -o errexit

# 1. Install Python deps via uv (Render has uv pre-installed in newer runtimes;
#    if not, fall back to pip).
if command -v uv >/dev/null 2>&1; then
    uv sync --frozen
    PYTHON_RUN="uv run"
else
    pip install --upgrade pip
    pip install -e .
    PYTHON_RUN=""
fi

# 2. Install Tailwind / daisyUI npm deps and compile production CSS.
$PYTHON_RUN python manage.py tailwind install
$PYTHON_RUN python manage.py tailwind build

# 3. Collect all static files into STATIC_ROOT (WhiteNoise serves them from there).
$PYTHON_RUN python manage.py collectstatic --noinput

# 4. Apply any pending database migrations.
$PYTHON_RUN python manage.py migrate --noinput