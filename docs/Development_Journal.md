# Development Journal

## 2026-07-03
- **Flutter SDK Configuration**: Manually linked the Flutter SDK path `C:\Users\ACER\development\flutter` inside the workspace settings (`.vscode/settings.json`).
- **Flutter Initialization**: Ran initial setup/build of the Flutter tool (Flutter version `3.44.4`, Dart SDK version `3.12.2`).
- **Dependencies Setup**: Executed `flutter pub get` inside the `mobile` directory to successfully resolve all Flutter dependencies.
- **Directory Structure Adjustments**:
  - Created top-level `assets/` and `notes/` directories.
  - Created `mobile/assets/` directory to support mobile asset management.
  - Initialized `docs/Development_Journal.md`.
- **Git Configuration**: Updated `.gitignore` to explicitly exclude `backend/venv/` and Flutter-generated folders (`.dart_tool/`, `build/`, etc.) in the `mobile` subdirectory.
