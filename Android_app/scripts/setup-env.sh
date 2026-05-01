#!/bin/bash
# Setup Android environment for Kiro

echo "Setting up Android environment..."

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.profile"
fi

# Check if already configured
if grep -q "ANDROID_HOME" "$SHELL_RC" 2>/dev/null; then
    echo "Android environment already configured in $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# Android SDK Configuration" >> "$SHELL_RC"
    echo "export ANDROID_HOME=\$HOME/Android/Sdk" >> "$SHELL_RC"
    echo "export PATH=\$PATH:\$ANDROID_HOME/platform-tools" >> "$SHELL_RC"
    echo "export PATH=\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin" >> "$SHELL_RC"
    echo "export PATH=\$PATH:\$ANDROID_HOME/emulator" >> "$SHELL_RC"
    echo "" >> "$SHELL_RC"
    echo "✓ Added Android environment to $SHELL_RC"
fi

echo ""
echo "Run this command to apply changes:"
echo "  source $SHELL_RC"
echo ""
echo "Then verify with:"
echo "  adb version"
