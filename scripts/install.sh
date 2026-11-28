#!/usr/bin/env bash
# Aether Vision installer.
#
# Designed for fresh machines: anything missing is installed.
#   - system packages (apt or dnf; uses sudo when not root)
#   - uv and a managed Python 3.12
#   - Python dependencies (locked versions)
#   - Node.js (local copy in .tools/ if the system one is missing or too old)
#   - the web dashboard
#   - RealSense udev rules (Linux)
#   - on a Qualcomm QCS6490 (e.g. RUBIK Pi 3): Qualcomm's AI packages
#     (QNN runtime + libQnnTFLiteDelegate.so) and the LiteRT release they are validated with
# Optionally installs a systemd service. Safe to re-run: every step is idempotent.
#
# Usage: scripts/install.sh [options]      (run with --help for the list)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGINAL_PATH="${PATH}"
export NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false
SERVICE_NAME="aether-vision"
UDEV_RULES_URL_TEMPLATE="https://raw.githubusercontent.com/IntelRealSense/librealsense/%s/config/99-realsense-libusb.rules"
UDEV_RULES_PATH="/etc/udev/rules.d/99-realsense-libusb.rules"
MIN_GLIBC="2.35"   # pyntcore wheels are built for manylinux_2_35
MIN_NODE_VERSION="20.19.0"
NODE_CHANNEL="latest-v22.x"   # LTS line used when Node.js has to be installed
TOOLS_DIR="${REPO_DIR}/.tools"

# Packages the runtime needs from the OS (pyrealsense2 links libusb and libudev).
APT_PACKAGES=(curl ca-certificates tar xz-utils libusb-1.0-0 libudev1 udev)
DNF_PACKAGES=(curl ca-certificates tar xz libusb1 systemd-libs systemd-udev)

# Qualcomm AI packages for the QCS6490 NPU (the CAM/AI set from the RUBIK Pi 3
# setup script, without its demo apps and desktop pieces).
QCOM_APT_PACKAGES=(libqnn-dev qnn-tools tensorflow-lite-qcom-apps qcom-adreno1
    qcom-fastcv-binaries-dev qcom-libdmabufheap-dev)
RUBIKPI_REPO_URL="http://apt.thundercomm.com/rubik-pi-3"
RUBIKPI_KEY_URL="https://thundercomm.s3.dualstack.ap-northeast-1.amazonaws.com/uploads/web/rubik-pi-3/tools/key.asc"
RUBIKPI_LIST_PATH="/etc/apt/sources.list.d/rubikpi3.list"
RUBIKPI_KEY_PATH="/etc/apt/trusted.gpg.d/rubikpi3.asc"
QCOM_PPA="ppa:ubuntu-qcom-iot/qcom-ppa"   # Qualcomm's PPA for other QCS6490 Ubuntu boards

# ----------------------------------------------------------------- options
WITH_FRONTEND=1
WITH_REALSENSE=1
WITH_DEV=0
WITH_UDEV=1
WITH_SYSTEM_PACKAGES=1
WITH_SERVICE=0
WITH_MOCK_CONFIG=0
RUN_TESTS=0
QCS6490="auto"   # auto | yes | no
IS_QCS6490=0
IS_RUBIKPI=0

usage() {
    cat <<USAGE
Aether Vision installer

Usage: scripts/install.sh [options]

Components (installed by default):
  --no-frontend          Skip the web dashboard (and Node.js)
  --no-realsense         Skip the Intel RealSense SDK (pyrealsense2) and its udev rules
  --no-udev              Skip the RealSense udev rules (needed to use the camera without root)
  --no-system-packages   Do not install OS packages (${APT_PACKAGES[*]}),
                         including the Qualcomm AI packages on a QCS6490

QCS6490 (detected automatically from the device tree):
  --qcs6490              Treat this machine as a QCS6490 even if detection fails
  --no-qcs6490           Ignore a detected QCS6490 (generic install, no Qualcomm packages)

Optional:
  --dev                  Also install development tools (pytest, mypy, ruff)
  --service              Install and start a systemd service that runs on boot
  --mock-config          Write config/config.json for the mock camera if no config exists
  --test                 Run the test suite after installing (implies --dev)
  -h, --help             Show this help

Steps that change the system (OS packages, udev rules, service) use sudo
when not run as root.

Examples:
  scripts/install.sh                          # coprocessor install
  scripts/install.sh --service                # coprocessor install, start on boot
  scripts/install.sh --dev --mock-config      # development machine without a camera
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-frontend) WITH_FRONTEND=0 ;;
        --no-realsense) WITH_REALSENSE=0 ;;
        --no-udev) WITH_UDEV=0 ;;
        --no-system-packages) WITH_SYSTEM_PACKAGES=0 ;;
        --qcs6490) QCS6490="yes" ;;
        --no-qcs6490) QCS6490="no" ;;
        --dev) WITH_DEV=1 ;;
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
    if [[ $EUID -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "Root privileges are needed for: $*. Run as root or install sudo."
    fi
}

download() {  # download URL DEST
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --tries=3 -O "$2" "$1"
    else
        die "Neither curl nor wget is available"
    fi
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

apt_missing() {  # apt_missing PKG...  ->  prints the packages that are not installed
    local pkg
    for pkg in "$@"; do
        dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null | grep -q "install ok installed" \
            || echo "${pkg}"
    done
}

device_tree_matches() {  # device_tree_matches REGEX  ->  true if the board identity matches
    local file
    for file in /proc/device-tree/compatible /proc/device-tree/model /sys/devices/soc0/machine; do
        [[ -r "${file}" ]] && tr '\0' '\n' < "${file}" | grep -qiE "$1" && return 0
    done
    return 1
}

find_qnn_delegate() {  # prints the path of libQnnTFLiteDelegate.so, if installed
    local found=""
    if command -v ldconfig >/dev/null 2>&1; then
        found="$(ldconfig -p 2>/dev/null | grep -m1 -oE '/[^ ]*libQnnTFLiteDelegate\.so' || true)"
    fi
    if [[ -z "${found}" ]]; then
        found="$(find /usr/lib /usr/local/lib /opt -name 'libQnnTFLiteDelegate.so' -print -quit \
            2>/dev/null || true)"
    fi
    echo "${found}"
}

# ----------------------------------------------------------------- steps
detect_qcs6490() {
    case "${QCS6490}" in
        yes) IS_QCS6490=1 ;;
        no) IS_QCS6490=0 ;;
        *)
            [[ "$(uname -s)" == "Linux" && "$(uname -m)" == "aarch64" ]] \
                && device_tree_matches 'qc[ms]6490' && IS_QCS6490=1
            ;;
    esac
    [[ ${IS_QCS6490} -eq 1 ]] && device_tree_matches 'rubik[ _-]?pi' && IS_RUBIKPI=1
    if [[ ${IS_QCS6490} -eq 1 ]]; then
        local board="QCS6490"
        [[ ${IS_RUBIKPI} -eq 1 ]] && board="QCS6490 (RUBIK Pi 3)"
        ok "${board}: will set up NPU inference (LiteRT + QNN delegate)"
    fi
    return 0
}

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
    detect_qcs6490
}

install_system_packages() {
    step "Checking system packages"
    if [[ "$(uname -s)" != "Linux" ]]; then
        info "Not Linux; skipped"
        return
    fi
    if [[ ${WITH_SYSTEM_PACKAGES} -eq 0 ]]; then
        info "Skipped (--no-system-packages)"
        return
    fi
    local missing=()
    if command -v apt-get >/dev/null 2>&1; then
        mapfile -t missing < <(apt_missing "${APT_PACKAGES[@]}")
        if [[ ${#missing[@]} -gt 0 ]]; then
            info "Installing: ${missing[*]}"
            as_root env DEBIAN_FRONTEND=noninteractive apt-get update -qq
            as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
                "${missing[@]}" >/dev/null
        fi
    elif command -v dnf >/dev/null 2>&1; then
        local pkg
        for pkg in "${DNF_PACKAGES[@]}"; do
            rpm -q "${pkg}" >/dev/null 2>&1 || missing+=("${pkg}")
        done
        if [[ ${#missing[@]} -gt 0 ]]; then
            info "Installing: ${missing[*]}"
            as_root dnf install -y -q "${missing[@]}"
        fi
    else
        warn "No apt-get or dnf found; make sure these are installed: ${APT_PACKAGES[*]}"
        return
    fi
    ok "System packages present"
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
    info "Installing uv (https://docs.astral.sh/uv/) into ~/.local/bin"
    local triple
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64) triple="x86_64-unknown-linux-gnu" ;;
        Linux-aarch64) triple="aarch64-unknown-linux-gnu" ;;
        Darwin-x86_64) triple="x86_64-apple-darwin" ;;
        Darwin-arm64) triple="aarch64-apple-darwin" ;;
        *) die "No uv build for $(uname -s) $(uname -m)" ;;
    esac
    # The release archive the official installer uses, verified against its checksum.
    local base="https://github.com/astral-sh/uv/releases/latest/download"
    local archive="uv-${triple}.tar.gz"
    local tmp
    tmp="$(mktemp -d)"
    download "${base}/${archive}" "${tmp}/${archive}"
    download "${base}/${archive}.sha256" "${tmp}/${archive}.sha256"
    [[ "$(sha256_of "${tmp}/${archive}")" == "$(awk '{print $1}' "${tmp}/${archive}.sha256")" ]] \
        || die "Checksum mismatch for ${archive}"
    tar -xzf "${tmp}/${archive}" -C "${tmp}"
    mkdir -p "${HOME}/.local/bin"
    install -m 0755 "${tmp}/uv-${triple}/uv" "${tmp}/uv-${triple}/uvx" "${HOME}/.local/bin/"
    rm -rf "${tmp}"
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv installation failed"
    ok "uv $(uv --version | awk '{print $2}')"
}

install_python() {
    step "Installing Python environment"
    (cd "${REPO_DIR}" && uv python install --quiet) || die "Could not install Python"
    local args=(sync --locked --quiet)
    [[ ${WITH_DEV} -eq 1 ]] || args+=(--no-dev)
    # On QCS6490 use the LiteRT release Qualcomm's delegate is validated with.
    [[ ${IS_QCS6490} -eq 1 ]] && args+=(--extra qcs6490)
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

node_ok() {  # true if a usable Node.js is on PATH
    command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 \
        && version_ge "$(node --version | tr -d v)" "${MIN_NODE_VERSION}"
}

install_local_node() {
    local os arch ext
    case "$(uname -s)" in
        Linux) os="linux"; ext="tar.xz" ;;
        Darwin) os="darwin"; ext="tar.gz" ;;
        *) die "No Node.js build for $(uname -s)" ;;
    esac
    case "$(uname -m)" in
        x86_64 | amd64) arch="x64" ;;
        aarch64 | arm64) arch="arm64" ;;
        *) die "No Node.js build for architecture $(uname -m)" ;;
    esac
    local base="https://nodejs.org/dist/${NODE_CHANNEL}"
    local tmp name expected
    tmp="$(mktemp -d)"
    download "${base}/SHASUMS256.txt" "${tmp}/SHASUMS256.txt"
    name="$(grep -oE "node-v[0-9.]+-${os}-${arch}\.${ext}" "${tmp}/SHASUMS256.txt" | head -n1)"
    [[ -n "${name}" ]] || die "Could not find a Node.js build for ${os}-${arch}"
    expected="$(grep " ${name}\$" "${tmp}/SHASUMS256.txt" | awk '{print $1}')"
    info "Downloading ${name}"
    download "${base}/${name}" "${tmp}/${name}"
    [[ "$(sha256_of "${tmp}/${name}")" == "${expected}" ]] || die "Checksum mismatch for ${name}"
    rm -rf "${TOOLS_DIR}/node"
    mkdir -p "${TOOLS_DIR}/node"
    tar -xf "${tmp}/${name}" -C "${TOOLS_DIR}/node" --strip-components=1
    rm -rf "${tmp}"
}

ensure_node() {
    # A previous run may have installed a local copy.
    [[ -x "${TOOLS_DIR}/node/bin/node" ]] && export PATH="${TOOLS_DIR}/node/bin:${PATH}"
    if node_ok; then
        ok "Node.js $(node --version) ($(command -v node))"
        return
    fi
    if command -v node >/dev/null 2>&1; then
        info "Node.js $(node --version) is older than ${MIN_NODE_VERSION}; installing a local copy"
    else
        info "Node.js not found; installing a local copy"
    fi
    install_local_node
    export PATH="${TOOLS_DIR}/node/bin:${PATH}"
    node_ok || die "Node.js installation failed"
    ok "Node.js $(node --version) installed in .tools/node"
}

build_frontend() {
    step "Building web dashboard"
    if [[ ${WITH_FRONTEND} -eq 0 ]]; then
        info "Skipped (--no-frontend)"
        return
    fi
    ensure_node
    (cd "${REPO_DIR}/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent) \
        >/dev/null || die "Dashboard build failed"
    ok "Built frontend/dist"
}

install_udev_rules() {
    [[ ${WITH_UDEV} -eq 1 && ${WITH_REALSENSE} -eq 1 ]] || return 0
    [[ "$(uname -s)" == "Linux" ]] || return 0
    step "Installing RealSense udev rules"
    # Use the rules from the librealsense release matching the installed pyrealsense2.
    local version ref tmp
    version="$("${REPO_DIR}/.venv/bin/python" -c \
        'import importlib.metadata as m; print(".".join(m.version("pyrealsense2").split(".")[:3]))' \
        2>/dev/null || true)"
    ref="${version:+v${version}}"
    tmp="$(mktemp)"
    # shellcheck disable=SC2059 # the template is a constant
    if ! download "$(printf "${UDEV_RULES_URL_TEMPLATE}" "${ref:-master}")" "${tmp}"; then
        download "$(printf "${UDEV_RULES_URL_TEMPLATE}" master)" "${tmp}" \
            || die "Could not download RealSense udev rules"
    fi
    if [[ -f "${UDEV_RULES_PATH}" ]] && cmp -s "${tmp}" "${UDEV_RULES_PATH}"; then
        rm -f "${tmp}"
        ok "Already installed (${UDEV_RULES_PATH})"
        return
    fi
    as_root install -m 0644 "${tmp}" "${UDEV_RULES_PATH}"
    rm -f "${tmp}"
    if as_root udevadm control --reload-rules 2>/dev/null && as_root udevadm trigger 2>/dev/null; then
        ok "Installed ${UDEV_RULES_PATH} (librealsense ${ref:-master}); replug the camera"
    else
        warn "Installed ${UDEV_RULES_PATH}, but udev is not running (container?); reboot to apply"
    fi
}

add_qualcomm_repository() {
    if [[ ${IS_RUBIKPI} -eq 1 ]]; then
        # Thundercomm's RUBIK Pi 3 PPA (the one rubikpi-script/install_ppa_pkgs.sh adds).
        local codename
        codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
        if grep -rqs "apt.thundercomm.com/rubik-pi-3" /etc/apt/sources.list /etc/apt/sources.list.d/; then
            info "RUBIK Pi 3 package repository already configured"
            return 0
        fi
        [[ "${codename}" == "noble" ]] || {
            warn "The RUBIK Pi 3 repository is for Ubuntu 24.04 (noble); this is '${codename}'"
            return 1
        }
        info "Adding the RUBIK Pi 3 package repository"
        local tmp
        tmp="$(mktemp)"
        download "${RUBIKPI_KEY_URL}" "${tmp}" || { rm -f "${tmp}"; return 1; }
        as_root install -m 0644 "${tmp}" "${RUBIKPI_KEY_PATH}"
        rm -f "${tmp}"
        echo "deb ${RUBIKPI_REPO_URL}/${codename} ppa main" | as_root tee "${RUBIKPI_LIST_PATH}" >/dev/null
    else
        if grep -rqs "ubuntu-qcom-iot" /etc/apt/sources.list /etc/apt/sources.list.d/; then
            info "Qualcomm package repository already configured"
            return 0
        fi
        info "Adding the Qualcomm package repository (${QCOM_PPA})"
        if ! command -v add-apt-repository >/dev/null 2>&1; then
            as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                software-properties-common >/dev/null || return 1
        fi
        as_root add-apt-repository -y "${QCOM_PPA}" >/dev/null || return 1
    fi
    return 0
}

install_qualcomm_runtime() {
    # NPU inference needs libQnnTFLiteDelegate.so and the QNN HTP libraries.
    if [[ ${IS_QCS6490} -eq 0 ]]; then
        # Not a QCS6490: only report a runtime someone installed by hand.
        [[ "$(uname -s)" == "Linux" && "$(uname -m)" == "aarch64" ]] || return 0
        local found
        found="$(find_qnn_delegate)"
        [[ -n "${found}" ]] && ok "QNN delegate found: ${found}"
        return 0
    fi
    step "Installing Qualcomm AI runtime (NPU)"
    if [[ ${WITH_SYSTEM_PACKAGES} -eq 0 ]]; then
        info "Package installation skipped (--no-system-packages)"
    elif ! command -v apt-get >/dev/null 2>&1; then
        info "No apt-get; install the Qualcomm AI Engine Direct (QAIRT) runtime yourself"
    else
        local missing=()
        mapfile -t missing < <(apt_missing "${QCOM_APT_PACKAGES[@]}")
        if [[ ${#missing[@]} -gt 0 ]]; then
            if add_qualcomm_repository; then
                info "Installing: ${missing[*]}"
                as_root env DEBIAN_FRONTEND=noninteractive apt-get update -qq \
                    && as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                        "${missing[@]}" >/dev/null \
                    || warn "Could not install the Qualcomm AI packages (${missing[*]})"
            else
                warn "Could not add the Qualcomm package repository"
            fi
        else
            ok "Qualcomm AI packages present"
        fi
    fi
    local found
    found="$(find_qnn_delegate)"
    if [[ -n "${found}" ]]; then
        ok "QNN delegate: ${found}"
    else
        warn "libQnnTFLiteDelegate.so not found; the detector will fall back to the CPU." \
            "On a RUBIK Pi 3 run rubikpi-script's install_ppa_pkgs.sh. See docs/DEPLOYMENT.md"
    fi
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
    ok "Wrote config/config.json (mock camera)"
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
    local version
    version="$("${REPO_DIR}/.venv/bin/aether-vision" --version)" \
        || die "aether-vision failed to start"
    ok "aether-vision ${version} runs"
    if [[ ${RUN_TESTS} -eq 1 ]]; then
        (cd "${REPO_DIR}" && uv run --locked pytest -q) || die "Tests failed"
        ok "Tests passed"
    fi
}

summary() {
    step "Done"
    if [[ ${WITH_SERVICE} -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
        info "Running as a service:  systemctl status ${SERVICE_NAME}"
    elif PATH="${ORIGINAL_PATH}" command -v uv >/dev/null 2>&1; then
        info "Start:          ${BOLD}uv run aether-vision${RESET}"
    else
        info "Start:          ${BOLD}.venv/bin/aether-vision${RESET}"
        info "                (to use 'uv run', add ~/.local/bin to your PATH and open a new shell)"
    fi
    info "Dashboard:      http://$(hostname 2>/dev/null || echo localhost):5803"
    if [[ -e "${REPO_DIR}/config/config.json" ]]; then
        info "Configuration:  config/config.json"
    else
        info "Configuration:  config/config.json (written with defaults on first start)"
    fi
    if [[ ${IS_QCS6490} -eq 1 ]]; then
        info "NPU:            put a quantized .tflite model in models/ and set detector.model_path"
    fi
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo
        echo "${YELLOW}Warnings:${RESET}"
        for warning in "${WARNINGS[@]}"; do echo "  - ${warning}"; done
    fi
}

check_platform
install_system_packages
ensure_uv
install_python
build_frontend
install_udev_rules
install_qualcomm_runtime
write_mock_config
install_service
verify
summary
