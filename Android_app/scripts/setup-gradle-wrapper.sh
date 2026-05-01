#!/bin/bash
# Setup Gradle Wrapper for the project

echo "Setting up Gradle Wrapper..."

# Install gradle temporarily if not available
if ! command -v gradle &> /dev/null; then
    echo "Installing Gradle via SDKMAN..."
    curl -s "https://get.sdkman.io" | bash
    source "$HOME/.sdkman/bin/sdkman-init.sh"
    sdk install gradle 8.5
fi

# Generate wrapper
cd "$(dirname "$0")/.."
gradle wrapper --gradle-version 8.5

echo "Gradle Wrapper setup complete!"
echo "You can now use ./gradlew commands"
