#!/usr/bin/env bash
# ===================================================================================================
# cooldx_install.sh - Installation Script for cooldx
# ===================================================================================================

# Exit on error, undefined vars and pipe failures
set -euo pipefail

# ===================================================================================================
# Configuration
# ===================================================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/lib/cooldx"
CONFIG_DIR="/etc/cooldx"
SYSTEMD_DIR="/etc/systemd/system"

SCRIPT_FILENAME="cooldx.py"
CONFIG_FILENAME="cooldx_config.json"
SERVICE_FILENAME="cooldx.service"

# Source files (relative to script location)
SOURCE_SCRIPT="${SCRIPT_DIR}/${SCRIPT_FILENAME}"
SOURCE_CONFIG="${SCRIPT_DIR}/${CONFIG_FILENAME}"
SOURCE_SERVICE="${SCRIPT_DIR}/${SERVICE_FILENAME}"

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
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# ===================================================================================================
# Validation
# ===================================================================================================
validate_sources() {
    
    if [[ ! -f "${SOURCE_SCRIPT}" ]]; then
        log_error "Source script not found: ${SOURCE_SCRIPT}"
        exit 1
    fi
    
    if [[ ! -f "${SOURCE_CONFIG}" ]]; then
        log_error "Config file not found: ${SOURCE_CONFIG}"
        exit 1
    fi
    
    if [[ ! -f "${SOURCE_SERVICE}" ]]; then
        log_error "Service file not found: ${SOURCE_SERVICE}"
        exit 1
    fi
    
    log_info "All source files validated..."
}

# ===================================================================================================
# Installation
# ===================================================================================================
install_daemon() {
    log_info "Installing cooldx daemon..."
    
    # Create installation directory
    mkdir -p "${INSTALL_DIR}"
    
    # Copy daemon script
    cp "${SOURCE_SCRIPT}" "${INSTALL_DIR}/${SCRIPT_FILENAME}"
    
    # Set ownership and permissions
    # 755: rwxr-xr-x (executable by all, writable by root only)
    chown root:root "${INSTALL_DIR}/${SCRIPT_FILENAME}"
    chmod 755 "${INSTALL_DIR}/${SCRIPT_FILENAME}"
}

install_config() {
    log_info "Installing configuration..."
    
    # Create config directory
    mkdir -p "${CONFIG_DIR}"
    
    # Copy config file (preserve existing if present)
    if [[ -f "${CONFIG_DIR}/${CONFIG_FILENAME}" ]]; then
        log_info "Existing config found. Creating backup..."
        BACKUP_FILE="${CONFIG_DIR}/$(date +%Y-%m-%d-%H%M%S)-cooldx_config_backup.json"
        cp "${CONFIG_DIR}/${CONFIG_FILENAME}" "${BACKUP_FILE}"
        log_info "Backup saved: ${BACKUP_FILE}"
    fi
    
    cp "${SOURCE_CONFIG}" "${CONFIG_DIR}/${CONFIG_FILENAME}"
    
    # Set ownership and permissions
    # 644: rw-r--r-- (readable by all, writable by root)
    chown root:root "${CONFIG_DIR}/${CONFIG_FILENAME}"
    chmod 644 "${CONFIG_DIR}/${CONFIG_FILENAME}"
}

install_service() {
    log_info "Installing systemd service..."
    
    # Copy service file
    cp "${SOURCE_SERVICE}" "${SYSTEMD_DIR}/${SERVICE_FILENAME}"
    
    # Set ownership and permissions
    # 644: rw-r--r-- (readable by all, writable by root)
    chown root:root "${SYSTEMD_DIR}/${SERVICE_FILENAME}"
    chmod 644 "${SYSTEMD_DIR}/${SERVICE_FILENAME}"
}

enable_service() {
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload
    
    log_info "Enabling cooldx service..."
    systemctl enable cooldx.service > /dev/null 2>&1
    
    if systemctl is-active --quiet cooldx.service; then
        log_info "Service is already running. Restarting to apply changes..."
        systemctl restart cooldx.service
    else
        log_info "Starting cooldx service..."
        systemctl start cooldx.service
    fi
    
    log_info "Checking service status..."
    if systemctl is-active --quiet cooldx.service; then
        log_success "cooldx service is running!"
    else
        log_error "cooldx service failed to start. Check: journalctl -u cooldx -e"
        exit 1
    fi
}

# ===================================================================================================
# Uninstall Function
# ===================================================================================================
uninstall() {
    log_info "Stopping and disabling cooldx service..."
    systemctl stop cooldx.service 2>/dev/null || true
    systemctl disable cooldx.service 2>/dev/null || true
    
    log_info "Removing installed files..."
    rm -f "${SYSTEMD_DIR}/${SERVICE_FILENAME}"
    rm -rf "${INSTALL_DIR}"
    rm -rf "${CONFIG_DIR}"
    
    systemctl daemon-reload
    
    echo ""
    echo "=================================================================="
    log_success "cooldx has been uninstalled."
    echo "=================================================================="
}

# ===================================================================================================
# Main
# ===================================================================================================
main() {
    echo "=================================================================="
    echo " cooldx | Cooling Daemon eXtended"
    echo "=================================================================="
    echo ""
    
    # Handle uninstall flag
    if [[ "${1:-}" == "--uninstall" ]]; then
        check_root
        uninstall
        exit 0
    fi
    
    check_root
    validate_sources
    
    echo ""
    log_info "The installation script will create the following:"
    echo "  - Daemon: '${INSTALL_DIR}/${SCRIPT_FILENAME}'"
    echo "  - Configuration: '${CONFIG_DIR}/${CONFIG_FILENAME}'"
    echo "  - Systemd unit: '${SYSTEMD_DIR}/${SERVICE_FILENAME}'"
    echo ""
    
    read -p "Continue with installation? [Y/N]: " confirm
    if [[ ! "${confirm,,}" =~ ^y(es)?$ ]]; then
        log_info "Installation cancelled."
        exit 0
    fi
    
    echo ""
    install_daemon
    install_config
    install_service
    enable_service
    
    echo ""
    echo "=================================================================="
    log_success "Installation complete!"
    echo "=================================================================="
    echo ""
}

main "$@"
