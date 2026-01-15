#!/bin/bash
###############################################################################
# OpenDuck Mini V3 - Firmware Flash Script
#
# Automated deployment script for Raspberry Pi Zero 2W
# Supports: Linux, macOS, WSL
#
# Usage:
#   ./flash.sh [OPTIONS]
#
# Options:
#   --host HOSTNAME     Target Raspberry Pi hostname or IP (default: openduck.local)
#   --user USERNAME     SSH username (default: pi)
#   --deploy-only       Skip tests, only deploy files
#   --test-only         Run tests without deploying
#   --verbose           Enable verbose output
#   --help              Show this help message
#
# Requirements:
#   - SSH access to Raspberry Pi
#   - rsync installed
#   - Python 3.9+ on target
#
# Safety:
#   - Creates backup before overwriting files
#   - Validates target is Raspberry Pi
#   - Runs basic health checks after deployment
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
REMOTE_HOST="${OPENDUCK_HOST:-openduck.local}"
REMOTE_USER="${OPENDUCK_USER:-pi}"
REMOTE_PATH="/home/${REMOTE_USER}/openduck"
DEPLOY_ONLY=false
TEST_ONLY=false
VERBOSE=false

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FIRMWARE_DIR="$(dirname "$SCRIPT_DIR")"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  OpenDuck Mini V3 - Firmware Flash Script${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

show_help() {
    cat << EOF
OpenDuck Mini V3 - Firmware Flash Script

Usage: ./flash.sh [OPTIONS]

Options:
  --host HOSTNAME     Target Raspberry Pi hostname or IP (default: openduck.local)
  --user USERNAME     SSH username (default: pi)
  --deploy-only       Skip tests, only deploy files
  --test-only         Run tests without deploying
  --verbose           Enable verbose output
  --help              Show this help message

Environment Variables:
  OPENDUCK_HOST       Override default host
  OPENDUCK_USER       Override default user

Examples:
  # Flash to default host (openduck.local)
  ./flash.sh

  # Flash to specific IP address
  ./flash.sh --host 192.168.1.100

  # Deploy only (no tests)
  ./flash.sh --deploy-only

  # Test only (no deployment)
  ./flash.sh --test-only

Requirements:
  - SSH access to Raspberry Pi
  - rsync installed
  - Python 3.9+ on target

EOF
}

###############################################################################
# Parse Command Line Arguments
###############################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            REMOTE_HOST="$2"
            shift 2
            ;;
        --user)
            REMOTE_USER="$2"
            shift 2
            ;;
        --deploy-only)
            DEPLOY_ONLY=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

###############################################################################
# Pre-flight Checks
###############################################################################

check_requirements() {
    print_info "Checking local requirements..."

    # Check rsync
    if ! command -v rsync &> /dev/null; then
        print_error "rsync not found. Install with:"
        echo "  Ubuntu/Debian: sudo apt install rsync"
        echo "  macOS: brew install rsync"
        exit 1
    fi
    print_success "rsync found"

    # Check SSH
    if ! command -v ssh &> /dev/null; then
        print_error "ssh not found"
        exit 1
    fi
    print_success "ssh found"

    # Check firmware directory structure
    if [[ ! -d "$FIRMWARE_DIR/src" ]]; then
        print_error "Firmware source directory not found: $FIRMWARE_DIR/src"
        exit 1
    fi
    print_success "Firmware directory structure valid"
}

check_remote_connection() {
    print_info "Checking connection to ${REMOTE_USER}@${REMOTE_HOST}..."

    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "echo 2>&1" &> /dev/null; then
        print_error "Cannot connect to ${REMOTE_USER}@${REMOTE_HOST}"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check hostname/IP: ping ${REMOTE_HOST}"
        echo "  2. Check SSH access: ssh ${REMOTE_USER}@${REMOTE_HOST}"
        echo "  3. Set up SSH keys: ssh-copy-id ${REMOTE_USER}@${REMOTE_HOST}"
        echo "  4. Check firewall settings"
        exit 1
    fi
    print_success "Connected to ${REMOTE_USER}@${REMOTE_HOST}"
}

check_remote_platform() {
    print_info "Validating target platform..."

    # Check if target is Raspberry Pi
    if ssh "${REMOTE_USER}@${REMOTE_HOST}" "grep -q 'Raspberry Pi' /proc/cpuinfo" 2>/dev/null; then
        print_success "Target is Raspberry Pi"
    else
        print_warning "Target may not be a Raspberry Pi"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Check Python version
    python_version=$(ssh "${REMOTE_USER}@${REMOTE_HOST}" "python3 --version 2>&1 | cut -d' ' -f2")
    print_info "Remote Python version: $python_version"

    # Check required Python version (3.9+)
    if [[ $(echo "$python_version" | cut -d. -f1) -lt 3 ]] || \
       [[ $(echo "$python_version" | cut -d. -f2) -lt 9 ]]; then
        print_error "Python 3.9+ required, found $python_version"
        exit 1
    fi
    print_success "Python version compatible"
}

###############################################################################
# Deployment
###############################################################################

create_backup() {
    print_info "Creating backup of existing firmware..."

    ssh "${REMOTE_USER}@${REMOTE_HOST}" bash << 'EOF'
        if [ -d ~/openduck/src ]; then
            backup_dir=~/openduck_backup_$(date +%Y%m%d_%H%M%S)
            cp -r ~/openduck "$backup_dir"
            echo "Backup created: $backup_dir"
        else
            echo "No existing installation to backup"
        fi
EOF
    print_success "Backup complete"
}

deploy_firmware() {
    print_info "Deploying firmware to ${REMOTE_HOST}..."

    # Create remote directory
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH}"

    # Rsync options
    RSYNC_OPTS="-avz --delete"
    if [[ "$VERBOSE" == true ]]; then
        RSYNC_OPTS="$RSYNC_OPTS --progress"
    else
        RSYNC_OPTS="$RSYNC_OPTS --quiet"
    fi

    # Deploy source code
    print_info "Syncing source code..."
    rsync $RSYNC_OPTS \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='.git' \
        "${FIRMWARE_DIR}/src/" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/src/"
    print_success "Source code deployed"

    # Deploy configuration files
    print_info "Syncing configuration files..."
    rsync $RSYNC_OPTS \
        "${FIRMWARE_DIR}/config/" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/config/"
    rsync $RSYNC_OPTS \
        "${FIRMWARE_DIR}/configs/" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/configs/"
    print_success "Configuration files deployed"

    # Deploy scripts
    print_info "Syncing scripts..."
    rsync $RSYNC_OPTS \
        "${FIRMWARE_DIR}/scripts/" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/scripts/"

    # Make scripts executable
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "chmod +x ${REMOTE_PATH}/scripts/*.py"
    print_success "Scripts deployed"

    # Deploy requirements.txt if exists
    if [[ -f "${FIRMWARE_DIR}/requirements.txt" ]]; then
        print_info "Deploying requirements.txt..."
        rsync $RSYNC_OPTS \
            "${FIRMWARE_DIR}/requirements.txt" \
            "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"
        print_success "requirements.txt deployed"
    fi
}

install_dependencies() {
    print_info "Installing Python dependencies..."

    ssh "${REMOTE_USER}@${REMOTE_HOST}" bash << 'EOF'
        cd ~/openduck
        if [ -f requirements.txt ]; then
            pip3 install --user -r requirements.txt
            echo "Dependencies installed"
        else
            echo "No requirements.txt found, skipping"
        fi
EOF
    print_success "Dependencies installed"
}

###############################################################################
# Testing
###############################################################################

run_tests() {
    print_info "Running hardware tests on ${REMOTE_HOST}..."

    ssh "${REMOTE_USER}@${REMOTE_HOST}" bash << 'EOF'
        cd ~/openduck
        python3 scripts/test_sensors.py
EOF

    if [[ $? -eq 0 ]]; then
        print_success "Hardware tests passed"
    else
        print_error "Hardware tests failed"
        print_warning "Check connections and try again"
        return 1
    fi
}

###############################################################################
# Main Execution
###############################################################################

main() {
    print_header

    # Pre-flight checks
    check_requirements
    check_remote_connection
    check_remote_platform

    echo ""

    # Test-only mode
    if [[ "$TEST_ONLY" == true ]]; then
        print_info "Running in test-only mode (no deployment)"
        run_tests
        exit $?
    fi

    # Deployment
    create_backup
    deploy_firmware
    install_dependencies

    echo ""
    print_success "Deployment complete!"

    # Run tests unless deploy-only
    if [[ "$DEPLOY_ONLY" == false ]]; then
        echo ""
        print_info "Running post-deployment tests..."
        run_tests
    fi

    # Success summary
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_success "Firmware successfully flashed to ${REMOTE_HOST}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. SSH to robot: ssh ${REMOTE_USER}@${REMOTE_HOST}"
    echo "  2. Calibrate servos: cd openduck && python3 scripts/calibrate_servos.py"
    echo "  3. Test robot: python3 scripts/test_sensors.py"
    echo ""
}

# Run main function
main
