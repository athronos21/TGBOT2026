#!/bin/bash

# MetaTrader 5 Setup Script for Linux
# This script helps set up MT5 on Linux using Wine

set -e

echo "=========================================="
echo "MetaTrader 5 Setup for Linux"
echo "=========================================="
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Error: This script is designed for Linux systems"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Wine is installed
if ! command_exists wine; then
    echo "Wine is not installed. Installing Wine..."
    sudo dpkg --add-architecture i386
    sudo apt-get update
    sudo apt-get install -y wine64 wine32 winetricks
    echo "Wine installed successfully!"
else
    echo "Wine is already installed: $(wine --version)"
fi

# Create downloads directory if it doesn't exist
DOWNLOAD_DIR="$HOME/Downloads"
mkdir -p "$DOWNLOAD_DIR"

# Download MT5 installer
MT5_INSTALLER="$DOWNLOAD_DIR/mt5setup.exe"
if [ ! -f "$MT5_INSTALLER" ]; then
    echo ""
    echo "Downloading MetaTrader 5 installer..."
    wget -O "$MT5_INSTALLER" https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
    echo "Download complete!"
else
    echo "MT5 installer already exists at $MT5_INSTALLER"
fi

# Install Wine dependencies
echo ""
echo "Installing Wine dependencies..."
winetricks -q vcrun2015 dotnet48 || echo "Some dependencies may have failed, but continuing..."

# Launch MT5 installer
echo ""
echo "Launching MT5 installer..."
echo "Please follow the installation wizard."
echo "Important: Enable 'Allow algorithmic trading' and 'Allow DLL imports' in settings!"
wine "$MT5_INSTALLER"

# Wait for installation to complete
echo ""
echo "Waiting for installation to complete..."
sleep 5

# Find MT5 installation path
MT5_PATH="$HOME/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"
if [ -f "$MT5_PATH" ]; then
    echo ""
    echo "=========================================="
    echo "MT5 Installation Complete!"
    echo "=========================================="
    echo "MT5 Path: $MT5_PATH"
    echo ""
    echo "Next steps:"
    echo "1. Launch MT5: wine '$MT5_PATH'"
    echo "2. Create a demo account with your broker"
    echo "3. Enable algorithmic trading in Tools → Options → Expert Advisors"
    echo "4. Update config.yaml with your MT5 credentials"
    echo "5. Install Python package: pip install MetaTrader5"
    echo ""
    echo "For detailed instructions, see: docs/MT5_SETUP.md"
else
    echo ""
    echo "=========================================="
    echo "Installation Status Unknown"
    echo "=========================================="
    echo "Could not find MT5 at expected path: $MT5_PATH"
    echo "Please check if installation was successful."
    echo "You may need to manually locate the MT5 installation."
    echo ""
    echo "For troubleshooting, see: docs/MT5_SETUP.md"
fi

echo ""
echo "=========================================="
echo "Alternative: Use Windows VPS"
echo "=========================================="
echo "For production trading, consider using a Windows VPS:"
echo "- Better stability and performance"
echo "- Lower latency to broker servers"
echo "- No Wine compatibility issues"
echo ""
echo "See docs/MT5_SETUP.md for VPS setup instructions."
echo ""
