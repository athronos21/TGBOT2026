# Android Development Guidelines

## Project Standards

### Code Style
- Follow Kotlin coding conventions
- Use meaningful variable and function names
- Keep functions small and focused
- Add comments for complex logic

### Architecture
- Use MVVM (Model-View-ViewModel) pattern
- Separate concerns: UI, business logic, data layer
- Use Repository pattern for data access
- Implement dependency injection with Hilt/Dagger

### Best Practices
- Use ViewBinding or Jetpack Compose for UI
- Handle lifecycle events properly
- Implement proper error handling
- Use Coroutines for async operations
- Follow Material Design guidelines

### Testing
- Write unit tests for ViewModels and business logic
- Use MockK for mocking in tests
- Implement UI tests with Espresso or Compose Testing

### Dependencies
- Keep dependencies up to date
- Use version catalogs for dependency management
- Minimize third-party libraries

## Build & Run
- Build: `./gradlew build`
- Run tests: `./gradlew test`
- Install debug: `./gradlew installDebug`
