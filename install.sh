#!/bin/bash

# Pak Installation Script
# Installs pak and ast_helper standalone executables

set -e

# Configuration
INSTALL_DIR="$HOME/bin"
DIST_DIR="$(dirname "$0")/dist"
EXECUTABLES=("pak" "ast_helper")

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
        log_warn "$INSTALL_DIR is not in your PATH"
        log_warn "Add this to your ~/.bashrc or ~/.zshrc:"
        echo "export PATH=\"\$HOME/bin:\$PATH\""
    fi
}

# Build executables using PyInstaller
build_executables() {
    log_info "Building standalone executables..."
    
    # Check if Poetry is available
    if command -v poetry &> /dev/null; then
        log_info "Using Poetry to build executables"
        poetry run pyinstaller --onefile pak.py
        poetry run pyinstaller --onefile ast_helper.py
    else
        log_info "Poetry not found, using pip/python directly"
        pip install pyinstaller
        pyinstaller --onefile pak.py
        pyinstaller --onefile ast_helper.py
    fi
}

# Install executables
install_executables() {
    if [[ ! -d "$DIST_DIR" ]]; then
        log_error "Distribution directory not found: $DIST_DIR"
        log_error "Run build first or ensure executables are built"
        exit 1
    fi
    
    for exe in "${EXECUTABLES[@]}"; do
        if [[ -f "$DIST_DIR/$exe" ]]; then
            log_info "Installing $exe to $INSTALL_DIR"
            cp "$DIST_DIR/$exe" "$INSTALL_DIR/"
            chmod +x "$INSTALL_DIR/$exe"
        else
            log_error "Executable not found: $DIST_DIR/$exe"
            exit 1
        fi
    done
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    for exe in "${EXECUTABLES[@]}"; do
        if [[ -x "$INSTALL_DIR/$exe" ]]; then
            log_info "$exe installed successfully"
            # Test if executable works
            if "$INSTALL_DIR/$exe" --version &> /dev/null; then
                log_info "$exe is working correctly"
            else
                log_warn "$exe may not be working correctly"
            fi
        else
            log_error "$exe installation failed"
            exit 1
        fi
    done
}

# Main installation process
main() {
    log_info "Starting Pak installation..."
    
    # Parse command line arguments
    BUILD_ONLY=false
    INSTALL_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build-only)
                BUILD_ONLY=true
                shift
                ;;
            --install-only)
                INSTALL_ONLY=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --build-only    Only build executables, don't install"
                echo "  --install-only  Only install existing executables"
                echo "  --help, -h      Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_project_dir
    
    if [[ "$INSTALL_ONLY" != true ]]; then
        build_executables
    fi
    
    if [[ "$BUILD_ONLY" != true ]]; then
        create_install_dir
        install_executables
        verify_installation
        check_path
        
        log_info "Installation completed successfully!"
        log_info "You can now use: pak and ast_helper"
    else
        log_info "Build completed. Executables are in $DIST_DIR"
    fi
}

# Run main function
main "$@"