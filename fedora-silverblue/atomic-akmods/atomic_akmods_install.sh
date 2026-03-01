#!/usr/bin/env bash
# ===================================================================================================
# atomic_akmods_install.sh - Build and layer the atomic-akmods RPM
# ===================================================================================================

# Exit on error, undefined vars and pipe failures
# -E (errtrace) ensures the ERR trap fires inside functions, not just the top-level shell
set -Eeuo pipefail

# ===================================================================================================
# Configuration
# ===================================================================================================
PACKAGE_NAME="atomic-akmods"

TOOLBOX_NAME="automated-atomic-akmods-builder"
TOOLBOX_USER="${SUDO_USER:-$USER}"
TOOLBOX_RUNTIME_DIR="/run/user/$(id -u "${TOOLBOX_USER}")"
BUILD_HOME="$(eval echo ~${TOOLBOX_USER})"
BUILD_DIR=""
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

CERT_FILENAME="public_key.der"
PKEY_FILENAME="private_key.priv"
SPEC_FILENAME="atomic_akmods.spec"

SRC_CERT="/etc/pki/akmods/certs/${CERT_FILENAME}"
SRC_PKEY="/etc/pki/akmods/private/${PKEY_FILENAME}"
SPEC_FILE="${SCRIPT_DIR}/${SPEC_FILENAME}"

# ===================================================================================================
# Helper Functions
# ===================================================================================================
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_success() {
    echo "[SUCCESS] $1"
}

check_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# ===================================================================================================
# Cleanup
# ===================================================================================================
# cleanup() removes the build directory and the toolbox container.
# It is called explicitly at the end of a successful run. 
# It is also bound to the ERR trap to ensure any early exit caused by set -e still removes all artifacts. 
# Nothing is left on the disk.
# The || true on toolbox rm prevents a failure if the container was never created.
cleanup() {
    [[ -n "${BUILD_DIR}" ]] && rm -rf "${BUILD_DIR}"
    sudo -u "${TOOLBOX_USER}" XDG_RUNTIME_DIR="${TOOLBOX_RUNTIME_DIR}" \
        toolbox rm --force "${TOOLBOX_NAME}" 2>/dev/null || true
}

trap 'log_error "Cleaning up..."; cleanup' ERR

# ===================================================================================================
# Validation
# ===================================================================================================
validate_sources() {

    [[ ! -f "${SRC_CERT}" ]] && { log_error "Missing: ${SRC_CERT}. Run: sudo kmodgenca -a"; exit 1; }
    [[ ! -f "${SRC_PKEY}" ]] && { log_error "Missing: ${SRC_PKEY}. Run: sudo kmodgenca -a"; exit 1; }
    [[ ! -f "${SPEC_FILE}" ]] && { log_error "Missing spec file: ${SPEC_FILE}"; exit 1; }

    command -v toolbox &>/dev/null || { log_error "toolbox not found. Pre-installed on Fedora Silverblue"; exit 1; }

    local _json _has_staged
    _json="$(rpm-ostree status --json 2>/dev/null)"
    _has_staged="$(echo "${_json}" | jq '[.deployments[] | select(.staged == true)] | length')"

    # Check if the package is already layered in either the staged or booted deployment to prevent conflicts.
    if [[ "${_has_staged}" -gt 0 ]]; then
        if echo "${_json}" | jq -e --arg pkg "${PACKAGE_NAME}" \
                '[.deployments[] | select(.staged == true)
                 | (.packages // []) + (."requested-local-packages" // []) + (."requested-packages" // [])
                 | .[] | select(startswith($pkg))] | length > 0' &>/dev/null; then
            log_error "'${PACKAGE_NAME}' is already layered in the staged deployment. Review with: 'rpm-ostree status'"
            exit 1
        fi
    else
        if echo "${_json}" | jq -e --arg pkg "${PACKAGE_NAME}" \
                '[.deployments[] | select(.booted == true)
                 | (.packages // []) + (."requested-local-packages" // []) + (."requested-packages" // [])
                 | .[] | select(startswith($pkg))] | length > 0' &>/dev/null; then
            log_error "'${PACKAGE_NAME}' is already layered in the booted deployment. Review with: 'rpm-ostree status'"
            exit 1
        fi
    fi

    # Confirm akmods is already layered in the booted deployment before proceeding.
    # MOK keys must be enrolled, which implies akmods was already installed.
    if ! echo "${_json}" | jq -e \
            '[.deployments[] | select(.booted == true) | (.packages // [])[] | select(. == "akmods")] | length > 0' &>/dev/null; then
        log_error "Install 'akmods' and ensure MOK signing keys are setup before running this script."
        exit 1
    fi

    log_info "All source files validated..."
}

# ===================================================================================================
# On the Host
# ===================================================================================================
stage_sources() {
    log_info "Creating build directory structure..."
    BUILD_DIR="$(mktemp -d "${BUILD_HOME}/.atomic-akmods-XXXXXX")"
    mkdir -p "${BUILD_DIR}"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

    log_info "Copying signing keys into SOURCES..."
    cp "${SRC_CERT}" "${BUILD_DIR}/SOURCES/${CERT_FILENAME}"
    cp "${SRC_PKEY}" "${BUILD_DIR}/SOURCES/${PKEY_FILENAME}"

    log_info "Setting permissions on private and public keys..."
    chmod 0400 "${BUILD_DIR}/SOURCES/${CERT_FILENAME}" "${BUILD_DIR}/SOURCES/${PKEY_FILENAME}"

    log_info "Copying spec file into SPECS..."
    cp "${SPEC_FILE}" "${BUILD_DIR}/SPECS/${SPEC_FILENAME}"

    chown -R "${TOOLBOX_USER}:${TOOLBOX_USER}" "${BUILD_DIR}"
    log_info "Sources staged to: ${BUILD_DIR}"
}

layer_rpm() {
    RPM_PATH="$(find "${BUILD_DIR}/RPMS" -name "${PACKAGE_NAME}-*.noarch.rpm" | head -1)"
    [[ -z "${RPM_PATH}" ]] && { log_error "RPM not found after build."; exit 1; }

    RPM_NAME="$(rpm -qp --qf '%{NAME}\n' "${RPM_PATH}")"
    [[ "${RPM_NAME}" != "${PACKAGE_NAME}" ]] && {
        log_error "Unexpected RPM name: ${RPM_NAME} (Expected: ${PACKAGE_NAME})"
        exit 1
    }

    log_info "Layering '${PACKAGE_NAME}'..."
    rpm-ostree install "${RPM_PATH}"
}

# ===================================================================================================
# Inside the Toolbox
# ===================================================================================================
toolbox_create() {
    if ! sudo -u "${TOOLBOX_USER}" XDG_RUNTIME_DIR="${TOOLBOX_RUNTIME_DIR}" \
            toolbox list --containers 2>/dev/null | grep -q "${TOOLBOX_NAME}"; then
        log_info "Creating toolbox '${TOOLBOX_NAME}'..."
        sudo -u "${TOOLBOX_USER}" XDG_RUNTIME_DIR="${TOOLBOX_RUNTIME_DIR}" \
            toolbox create --container "${TOOLBOX_NAME}" >/dev/null
    else
        log_info "Toolbox '${TOOLBOX_NAME}' already exists."
    fi
}

toolbox_install_deps() {
    log_info "Installing RPM build tools in the toolbox..."
    sudo -u "${TOOLBOX_USER}" XDG_RUNTIME_DIR="${TOOLBOX_RUNTIME_DIR}" \
        toolbox run --container "${TOOLBOX_NAME}" sudo dnf install -y --quiet rpmdevtools >/dev/null 2>&1
}

build_rpm() {
    log_info "Building '${PACKAGE_NAME}' RPM in the toolbox..."
    sudo -u "${TOOLBOX_USER}" XDG_RUNTIME_DIR="${TOOLBOX_RUNTIME_DIR}" \
        toolbox run --container "${TOOLBOX_NAME}" \
        rpmbuild --define "_topdir ${BUILD_DIR}" -bb "${BUILD_DIR}/SPECS/${SPEC_FILENAME}" >/dev/null 2>&1
}

# ===================================================================================================
# Main
# ===================================================================================================
main() {
    echo "=================================================================="
    echo " atomic-akmods | MOK Key Packaging for OSTree"
    echo "=================================================================="
    echo ""

    check_root
    validate_sources

    echo ""
    echo "The installation script will create the following:"
    echo "  - Layered RPM: '${PACKAGE_NAME}'"
    echo "  - Toolbox container: '${TOOLBOX_NAME}' (removed after build)"
    echo ""

    read -p "Continue with installation? [Y/N]: " confirm
    if [[ ! "${confirm,,}" =~ ^y(es)?$ ]]; then
        log_info "Installation cancelled."
        exit 0
    fi

    echo ""
    stage_sources

    echo ""
    toolbox_create
    toolbox_install_deps
    build_rpm

    echo ""
    echo "================================="
    layer_rpm
    echo "================================="

    cleanup

    echo ""
    echo "=================================================================="
    log_success "Installation complete!"
    echo "=================================================================="
}

main "$@"
