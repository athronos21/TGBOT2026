# Android Development in Kiro IDE

You can develop Android apps entirely in Kiro without Android Studio!

## What You Have
✅ Java 21 (OpenJDK) - Ready to go

## What You Need to Install

### 1. Android SDK Command Line Tools

```bash
# Download Android command line tools
cd ~
mkdir -p android-sdk/cmdline-tools
cd android-sdk/cmdline-tools

# Download latest command line tools (Linux)
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip commandlinetools-linux-11076708_latest.zip
mv cmdline-tools latest

# Set environment variables (add to ~/.bashrc or ~/.zshrc)
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/emulator

# Reload shell
source ~/.bashrc
```

### 2. Install SDK Packages

```bash
# Accept licenses
sdkmanager --licenses

# Install essential packages
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# Optional: Install emulator
sdkmanager "emulator" "system-images;android-34;google_apis;x86_64"
```

### 3. Gradle Wrapper (Already Included)

Your project uses Gradle Wrapper, so no separate Gradle installation needed!

```bash
# Make gradlew executable
cd Android_app
chmod +x gradlew

# Build your app
./gradlew build
```

## Development Workflow in Kiro

### Build & Test
```bash
# Build debug APK
./gradlew assembleDebug

# Run unit tests
./gradlew test

# Run instrumented tests (requires device/emulator)
./gradlew connectedAndroidTest

# Clean build
./gradlew clean
```

### Install on Device
```bash
# Connect your Android device via USB (enable USB debugging)
# Or start an emulator

# Install debug APK
./gradlew installDebug

# Or manually install
adb install app/build/outputs/apk/debug/app-debug.apk
```

### Useful ADB Commands
```bash
# List connected devices
adb devices

# View logs
adb logcat

# Clear app data
adb shell pm clear com.example.androidapp

# Uninstall app
adb uninstall com.example.androidapp
```

## Kiro Features for Android Development

### 1. Code Editing
- Full Kotlin syntax support
- Auto-completion and IntelliSense
- Code navigation and refactoring

### 2. XML Editing
- Layout file editing
- Resource file management

### 3. Build Integration
- Run Gradle commands from terminal
- View build output in Kiro

### 4. Debugging
- Use `adb logcat` for logs
- Set up remote debugging if needed

### 5. Version Control
- Git integration built into Kiro
- Commit, push, pull directly from IDE

## Alternative: Use Physical Device

The easiest way to test without emulator:

1. Enable Developer Options on your Android phone
2. Enable USB Debugging
3. Connect via USB
4. Run `adb devices` to verify connection
5. Run `./gradlew installDebug` to install

## Quick Start

```bash
cd Android_app

# Make gradlew executable
chmod +x gradlew

# Build the project
./gradlew build

# If you have a device connected
./gradlew installDebug
```

## Tips

- Use Kiro's terminal for all Gradle commands
- Keep `adb logcat` running in a separate terminal for real-time logs
- Use Kiro's file explorer to navigate project structure
- Leverage Kiro's AI assistance for code generation and debugging
