#!/bin/bash
set -euo pipefail

PY_REQ_TXT=./config/requirements.txt
VENV_ROOT=./.venv
DOT_GIT_FILE=./.git
DOT_GIT_EXCLUDE_LIST=(
    "__pycache__"
    ".history"
    ".venv"
)

# ---------------------------------------------------------------------------
# Detect package manager
# ---------------------------------------------------------------------------
if command -v uv &>/dev/null; then
    USE_UV=true
    echo "[✓] 检测到 uv"
else
    USE_UV=false
    echo "[i] 未检测到 uv，使用 pip"
fi

# ---------------------------------------------------------------------------
# Create virtual environment
# ---------------------------------------------------------------------------
if [ -d "${VENV_ROOT}" ]; then
    echo "${VENV_ROOT} already exists"
elif $USE_UV; then
    echo "Creating ${VENV_ROOT} with uv"
    uv venv "${VENV_ROOT}"
else
    echo "Creating ${VENV_ROOT}"
    python -m venv "${VENV_ROOT}"
fi

# ---------------------------------------------------------------------------
# Activate venv
# ---------------------------------------------------------------------------
case "$OSTYPE" in
    linux-gnu) source "${VENV_ROOT}/bin/activate" ;;
    *)         source "${VENV_ROOT}/Scripts/activate" ;;
esac

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------
if $USE_UV; then
    uv pip install -r "${PY_REQ_TXT}"
else
    python -m pip install --upgrade pip
    pip install -r "${PY_REQ_TXT}"
    pip install pip-system-certs --use-feature=truststore
    pip install --upgrade certifi
fi

# ---------------------------------------------------------------------------
# Configure git exclude
# ---------------------------------------------------------------------------
if [ -d "${DOT_GIT_FILE}" ]; then
    exclude_file="${DOT_GIT_FILE}/info/exclude"

    found=0
    if [ -f "${exclude_file}" ]; then
        for pattern in "${DOT_GIT_EXCLUDE_LIST[@]}"; do
            if grep -qF "${pattern}" "${exclude_file}"; then
                found=1
                break
            fi
        done
    fi

    printf -v joined '%s, ' "${DOT_GIT_EXCLUDE_LIST[@]}"
    if [ $found -eq 1 ]; then
        echo "git exclude already contains ${joined%, }"
    else
        echo
        printf "%s\n" "${DOT_GIT_EXCLUDE_LIST[@]}" >> "${exclude_file}"
        echo "Added ${joined%, } to git exclude"
    fi
fi
