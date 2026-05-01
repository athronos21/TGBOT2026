# Android App Project

## Overview
Native Android application built with Kotlin and modern Android development practices.

## Structure
- `app/` - Android app source code
  - `src/main/java/` - Kotlin source files
  - `src/main/res/` - Resources (layouts, values, drawables)
  - `src/androidTest/` - Instrumented tests
  - `src/test/` - Unit tests
- `docs/` - Documentation
- `assets/` - Images, icons, and resources
- `scripts/` - Build and deployment scripts
- `.kiro/` - Kiro IDE configuration and steering files

## Tech Stack
- Kotlin
- AndroidX libraries
- Material Design Components
- ViewBinding
- Coroutines
- MVVM Architecture

## Getting Started

### Prerequisites
- Android Studio or Kiro IDE
- JDK 17+
- Android SDK (API 24+)

### Build Commands
```bash
# Build the project
./gradlew build

# Run tests
./gradlew test

# Install debug APK
./gradlew installDebug

# Clean build
./gradlew clean
```

## Development Guidelines
See `.kiro/steering/android-development.md` for coding standards and best practices.

## License
[Add license information]
