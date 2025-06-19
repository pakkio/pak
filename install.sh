#!/bin/bash

# Pak Installation Script
# Installs pak and ast_helper standalone executables

set -e

# Configuration
INSTALL_DIR="$HOME/bin"
# Assuming DIST_DIR is where PyInstaller puts the executables, typically 'dist' in the project root
DIST_DIR="$(dirname "$0")/dist" 
PYTHON_SHARED_LIB_PATH="/usr/lib/x86_64-linux-gnu/libpython3.12.so.1.0" # VERIFY THIS PATH!

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running from project directory
check_project_dir() {
    if [[ ! -f "pak.py" || ! -f "ast_helper.py" ]]; then
        log_error "This script must be run from the pak project root directory"
        exit 1
    fi
}

# Create installation directory
create_install_dir() {
    if [[ ! -d "$INSTALL_DIR" ]]; then
        log_info "Creating installation directory: $INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
    fi
}

# Check if PATH includes install directory
check_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        log_warn "$INSTALL_DIR is not in your PATH."
        log_warn "You might need to add it to your shell configuration file (e.g., ~/.bashrc, ~/.zshrc):"
        echo "       export PATH=\"\$HOME/bin:\$PATH\""
        log_warn "And then source the file or open a new terminal."
    fi
}

# Build executables using PyInstaller
build_executables() {
    log_info "Building standalone executables..."

    if [ ! -f "${PYTHON_SHARED_LIB_PATH}" ]; then
        log_error "Python shared library not found at ${PYTHON_SHARED_LIB_PATH}"
        log_error "Please verify the PYTHON_SHARED_LIB_PATH in this script or install the required Python development packages."
        log_error "e.g., for Debian/Ubuntu: sudo apt-get install libpython3.12-dev"
        exit 1
    fi

    if command -v poetry &> /dev/null; then
        log_info "Using Poetry to build executables"
        
        # Build pak.py
        if [ -f pak.spec ]; then
            log_info "Building pak using pak.spec (ensure it includes shared lib fix if needed)"
            poetry run pyinstaller pak.spec
        else
            log_info "Building pak directly with shared library fix"
            poetry run pyinstaller --onefile --add-binary "${PYTHON_SHARED_LIB_PATH}:." pak.py
        fi

        # Build ast_helper.py with the explicit shared library fix
        log_info "Building ast_helper with shared library fix"
        poetry run pyinstaller --onefile --add-binary "${PYTHON_SHARED_LIB_PATH}:." ast_helper.py
    else
        log_error "Poetry not found. Please install Poetry or build manually."
        log_error "Manual build example for ast_helper:"
        log_error "  pyinstaller --onefile --add-binary \"${PYTHON_SHARED_LIB_PATH}:.\" ast_helper.py"
        exit 1
    fi
    log_info "Builds completed. Executables should be in ${DIST_DIR}/"
}

# Install executables to target directory
install_executables() {
    if [ ! -d "$DIST_DIR" ]; then
        log_error "Distribution directory '$DIST_DIR' not found. Build might have failed."
        exit 1
    fi

    for exe_name in "pak" "ast_helper"; do
        if [ -f "$DIST_DIR/$exe_name" ]; then
            log_info "Installing $exe_name to $INSTALL_DIR"
            cp "$DIST_DIR/$exe_name" "$INSTALL_DIR/$exe_name"
            chmod +x "$INSTALL_DIR/$exe_name"
        else
            log_error "Executable $exe_name not found in $DIST_DIR. Build might have failed."
            exit 1
        fi
    done
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    local all_verified=true

    # Verify pak
    if command -v pak &> /dev/null; then
        local pak_version
        pak_version=$(pak --version 2>/dev/null)
        if [ $? -eq 0 ] && [[ -n "$pak_version" ]]; then
            log_info "pak installed successfully and is working correctly (version: $pak_version)"
        else
            log_warn "pak command found, but 'pak --version' failed or returned empty. Exit code: $?"
            log_warn "Please check the executable at ${INSTALL_DIR}/pak"
            all_verified=false
        fi
    else
        log_warn "pak command not found in PATH after installation."
        log_warn "Please check your PATH and the executable at ${INSTALL_DIR}/pak"
        all_verified=false
    fi

    # Verify ast_helper
    if command -v ast_helper &> /dev/null; then
        log_info "ast_helper installed successfully."
        # Test by running it; it should print usage to stderr and exit with 2 if no args
        if (ast_helper > /dev/null 2>&1) || [ $? -eq 2 ]; then
            log_info "ast_helper appears to load and execute correctly (may show usage error, which is expected without arguments)."
        else
            log_warn "ast_helper command found, but execution test failed unexpectedly. Exit code: $?"
            log_warn "Please check the executable at ${INSTALL_DIR}/ast_helper"
            all_verified=false
        fi
    else
        log_warn "ast_helper command not found in PATH after installation."
        log_warn "Please check your PATH and the executable at ${INSTALL_DIR}/ast_helper"
        all_verified=false
    fi

    if $all_verified; then
        log_info "All main executables verified successfully!"
    else
        log_warn "Some verifications failed. Please review the warnings."
    fi
}


# Main script execution
main() {
    log_info "Starting Pak tool installation script..."
    check_project_dir
    create_install_dir
    
    build_executables
    install_executables
    
    verify_installation # Verification now happens after installation
    check_path          # Check PATH at the end as a reminder

    log_info "Installation process completed!"
    log_info "If you had to add $INSTALL_DIR to your PATH, you might need to source your shell configuration (e.g., source ~/.bashrc) or open a new terminal session."
}

# Run the main function
main
