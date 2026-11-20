#!/usr/bin/env bash
# Aether Vision installer.
#
# Installs uv (if missing), the Python environment, and the web dashboard.
# Optionally installs RealSense udev rules and a systemd service.
# Safe to re-run: every step is idempotent.
#
# Usage: scripts/install.sh [options]      (run with --help for the list)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="aether-vision"
UDEV_RULES_URL="https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules"
UDEV_RULES_PATH="/etc/udev/rules.d/99-realsense-libusb.rules"
MIN_GLIBC="2.35"   # pyntcore wheels are built for manylinux_2_35
MIN_NODE_MAJOR=20

# ----------------------------------------------------------------- options
WITH_FRONTEND=1
WITH_REALSENSE=1
WITH_LITERT=1
WITH_DEV=0
WITH_UDEV=0
WITH_SERVICE=0
WITH_MOCK_CONFIG=0
RUN_TESTS=0

usage() {
    cat <<USAGE
Aether Vision installer

Usage: scripts/install.sh [options]

Components (installed by default):
  --no-frontend      Skip building the web dashboard (needs Node.js >= ${MIN_NODE_MAJOR})
  --no-realsense     Skip the Intel RealSense SDK (pyrealsense2)
  --no-litert        Skip LiteRT (TFLite runtime used for the QCS6490 NPU)

Optional:
  --dev              Also install development tools (pytest, mypy, ruff)
  --udev             Install RealSense udev rules so the camera works without root (sudo)
  --service          Install and start a systemd service that runs on boot (sudo)
  --mock-config      Write config/config.json for the mock camera if no config exists
  --test             Run the test suite after installing (implies --dev)
  -h, --help         Show this help

Examples:
  scripts/install.sh                          # coprocessor install
  scripts/install.sh --udev --service         # coprocessor install, start on boot
  scripts/install.sh --dev --mock-config      # development machine without a camera
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-frontend) WITH_FRONTEND=0 ;;
        --no-realsense) WITH_REALSENSE=0 ;;
        --no-litert) WITH_LITERT=0 ;;
        --dev) WITH_DEV=1 ;;
        --udev) WITH_UDEV=1 ;;
        --service) WITH_SERVICE=1 ;;
        --mock-config) WITH_MOCK_CONFIG=1 ;;
        --test) RUN_TESTS=1; WITH_DEV=1 ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# ----------------------------------------------------------------- output
if [[ -t 1 ]]; then
    BOLD=$'\e[1m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; RED=$'\e[31m'; RESET=$'\e[0m'
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
step() { echo; echo "${BOLD}==> $*${RESET}"; }
info() { echo "    $*"; }
ok() { echo "    ${GREEN}✓${RESET} $*"; }
warn() { echo "    ${YELLOW}!${RESET} $*"; WARNINGS+=("$*"); }
die() { echo "${RED}error:${RESET} $*" >&2; exit 1; }
WARNINGS=()

version_ge() {  # version_ge A B  ->  true if A >= B
    [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

as_root() {
    if [[ $EUID -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

# ----------------------------------------------------------------- steps
check_platform() {
    step "Checking platform"
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"
    info "OS: ${os}, architecture: ${arch}"
    case "${os}" in
        Linux)
            if command -v ldd >/dev/null 2>&1; then
                local glibc
                glibc="$(ldd --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+$' || true)"
                if [[ -n "${glibc}" ]] && ! version_ge "${glibc}" "${MIN_GLIBC}"; then
                    die "glibc ${glibc} found; ${MIN_GLIBC}+ is required (Ubuntu 22.04 or newer)"
                fi
                [[ -n "${glibc}" ]] && ok "glibc ${glibc}"
            fi
            ;;
        Darwin) warn "macOS is supported for development only (no QCS6490/udev/systemd)" ;;
        *) die "Unsupported OS: ${os}" ;;
    esac
    command -v curl >/dev/null 2>&1 || die "curl is required"
}

ensure_uv() {
    step "Checking uv"
    if ! command -v uv >/dev/null 2>&1 && [[ -x "${HOME}/.local/bin/uv" ]]; then
        export PATH="${HOME}/.local/bin:${PATH}"
    fi
    if command -v uv >/dev/null 2>&1; then
        ok "uv $(uv --version | awk '{print $2}')"
        return
    fi
    info "Installing uv (https://docs.astral.sh/uv/)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv installation failed"
    ok "uv $(uv --version | awk '{print $2}')"
}

install_python() {
    step "Installing Python environment"
    local args=(sync --locked)
    [[ ${WITH_DEV} -eq 1 ]] || args+=(--no-dev)
    [[ ${WITH_LITERT} -eq 1 ]] && args+=(--extra litert)
    [[ ${WITH_DEV} -eq 1 ]] && args+=(--extra reload)
    (
        cd "${REPO_DIR}"
        if [[ ${WITH_REALSENSE} -eq 1 ]]; then
            if uv "${args[@]}" --extra realsense; then
                ok "Installed with RealSense SDK"
                exit 0
            fi
            echo "    ${YELLOW}!${RESET} pyrealsense2 is unavailable for this platform; retrying without it" >&2
            exit 3
        fi
        uv "${args[@]}"
    ) || {
        local status=$?
        [[ ${status} -eq 3 ]] || die "Python dependency installation failed"
        (cd "${REPO_DIR}" && uv "${args[@]}") || die "Python dependency installation failed"
        warn "RealSense SDK not installed. Build librealsense with -DBUILD_PYTHON_BINDINGS=ON," \
            "then install it into ${REPO_DIR}/.venv"
    }
    ok "Python $("${REPO_DIR}/.venv/bin/python" -c 'import platform; print(platform.python_version())') at .venv/"
}

build_frontend() {
    step "Building web dashboard"
    if [[ ${WITH_FRONTEND} -eq 0 ]]; then
        info "Skipped (--no-frontend)"
        return
    fi
    if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
        warn "Node.js not found; dashboard not built. Install Node.js ${MIN_NODE_MAJOR}+ and re-run" \
            "(the API still works without it)"
        return
    fi
    local node_version
    node_version="$(node --version | tr -d v)"
    if ! version_ge "${node_version}" "20.19.0"; then
        warn "Node.js ${node_version} is too old (need 20.19+ or 22.12+); dashboard not built"
        return
    fi
    (cd "${REPO_DIR}/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent) \
        || die "Dashboard build failed"
    ok "Built frontend/dist (Node.js ${node_version})"
}

install_udev_rules() {
    [[ ${WITH_UDEV} -eq 1 ]] || return 0
    step "Installing RealSense udev rules"
    [[ "$(uname -s)" == "Linux" ]] || { warn "udev rules are Linux-only; skipped"; return; }
    local tmp
    tmp="$(mktemp)"
    curl -fsSL "${UDEV_RULES_URL}" -o "${tmp}" || die "Could not download udev rules"
    as_root install -m 0644 "${tmp}" "${UDEV_RULES_PATH}"
    rm -f "${tmp}"
    as_root udevadm control --reload-rules
    as_root udevadm trigger
    ok "Installed ${UDEV_RULES_PATH} (replug the camera)"
}

write_mock_config() {
    [[ ${WITH_MOCK_CONFIG} -eq 1 ]] || return 0
    step "Writing mock configuration"
    local target="${REPO_DIR}/config/config.json"
    if [[ -e "${target}" ]]; then
        info "config/config.json already exists; left unchanged"
        return
    fi
    mkdir -p "${REPO_DIR}/config"
    cp "${REPO_DIR}/examples/config.mock.json" "${target}"
    ok "Wrote config/config.json (mock camera, local NetworkTables server)"
}

install_service() {
    [[ ${WITH_SERVICE} -eq 1 ]] || return 0
    step "Installing systemd service"
    command -v systemctl >/dev/null 2>&1 || { warn "systemd not found; service not installed"; return; }
    local user unit tmp
    user="$(id -un)"
    unit="/etc/systemd/system/${SERVICE_NAME}.service"
    tmp="$(mktemp)"
    sed -e "s|@USER@|${user}|g" -e "s|@REPO_DIR@|${REPO_DIR}|g" \
        "${REPO_DIR}/deploy/aether-vision.service.in" > "${tmp}"
    as_root install -m 0644 "${tmp}" "${unit}"
    rm -f "${tmp}"
    as_root systemctl daemon-reload
    as_root systemctl enable --now "${SERVICE_NAME}"
    ok "Service ${SERVICE_NAME} enabled and started (user ${user})"
    info "Logs: journalctl -u ${SERVICE_NAME} -f"
}

verify() {
    step "Verifying"
    local pipelines
    pipelines="$("${REPO_DIR}/.venv/bin/aether-vision" pipelines | tr '\n' ' ')" \
        || die "aether-vision failed to start"
    ok "aether-vision runs; pipelines: ${pipelines}"
    if [[ ${RUN_TESTS} -eq 1 ]]; then
        (cd "${REPO_DIR}" && uv run --locked pytest -q) || die "Tests failed"
        ok "Tests passed"
    fi
}

summary() {
    step "Done"
    if [[ ${WITH_SERVICE} -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
        info "Running as a service:  systemctl status ${SERVICE_NAME}"
    else
        info "Start:          ${BOLD}uv run aether-vision run${RESET}"
    fi
    info "Dashboard:      http://$(hostname 2>/dev/null || echo localhost):5803"
    if [[ -e "${REPO_DIR}/config/config.json" ]]; then
        info "Configuration:  config/config.json"
    else
        info "Configuration:  config/config.json (written with defaults on first start)"
    fi
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo
        echo "${YELLOW}Warnings:${RESET}"
        for warning in "${WARNINGS[@]}"; do echo "  - ${warning}"; done
    fi
}

check_platform
ensure_uv
install_python
build_frontend
install_udev_rules
write_mock_config
install_service
verify
summary
