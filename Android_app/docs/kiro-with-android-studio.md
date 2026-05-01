# Using Kiro with Android Studio SDK

You have Android Studio installed, so you can use Kiro for coding and Android Studio's SDK for building!

## Setup Environment Variables

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Android SDK (from Android Studio)
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
export PATH=$PATH:$ANDROID_HOME/emulator
```

Then reload:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Verify Setup

```bash
# Check Android SDK
echo $ANDROID_HOME

# Check ADB
adb version

# Check available devices
adb devices
```

## Best of Both Worlds

### Use Kiro for:
- Fast code editing with AI assistance
- Quick file navigation
- Git operations
- Terminal commands
- Lightweight development

### Use Android Studio for:
- Visual layout editor
- APK Analyzer
- Profiler and debugging tools
- Emulator management (AVD Manager)
- Complex refactoring

## Workflow in Kiro

```bash
cd Android_app

# Build project
./gradlew build

# Install on device
./gradlew installDebug

# Run tests
./gradlew test

# View logs
adb logcat | grep "AndroidApp"
```

## Quick Commands

```bash
# List connected devices
adb devices

# Install APK
adb install app/build/outputs/apk/debug/app-debug.apk

# Clear app data
adb shell pm clear com.example.androidapp

# View real-time logs
adb logcat -c && adb logcat

# Take screenshot
adb shell screencap /sdcard/screen.png
adb pull /sdcard/screen.png
```

## Tips

1. Edit code in Kiro (faster, AI-powered)
2. Build and run from Kiro terminal
3. Use Android Studio when you need visual tools
4. Keep both IDEs pointing to the same project folder
5. Use Kiro's AI to generate boilerplate code quickly
