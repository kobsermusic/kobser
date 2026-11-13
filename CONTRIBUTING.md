# Contributing to kobser

## Project layout

```
middleware/          FastAPI backend (Python)
  main.py            app entry point
  routes/            HTTP endpoints
  services/          yt-dlp, ytmusicapi, Navidrome, tagging
  db.py              SQLite sessions and download history
  frontend/          Svelte web app (Vite)
android/             Android app (Kotlin, Jetpack Compose, Media3)
docker-compose.yml   Navidrome and the middleware
```

## Development setup

To run the backend and the web app in Docker:
```bash
cp .env.example .env      # set MUSIC_DIR
docker compose up -d --build
```

For the web app with live reload you need Node 20.19 or newer (or 22.12 or newer). The Vite dev server forwards `/api` to the running middleware:
```bash
cd middleware/frontend
npm install
npm run dev
```

The Android app needs a current Android Studio, because the project uses AGP 9.4, and JDK 17. The JDK bundled with Android Studio works. A command-line build needs Gradle 9.6 or newer:
```bash
cd android
JAVA_HOME=/path/to/jdk-17 gradle assembleDebug testDebugUnitTest
```

## Tests

CI runs the backend lint and tests on every change under `middleware/`:
```bash
cd middleware
pip install -r requirements-dev.txt
ruff check .
pytest
```

The Android unit tests run with `gradle testDebugUnitTest` and use plain JUnit, so code that needs tests should not depend on Android framework classes.

## Guidelines

- Match the style of the surrounding code. The backend uses plain FastAPI and the standard library, the web app is ordinary Svelte, and the Android app uses MVVM (`XxxScreen` with `XxxViewModel`) with Hilt.
- Keep pull requests small, describe what they change, and mention new settings or environment variables.
- Never commit `.env`, a `cookies.txt`, keystores or APKs.
- Don't add tracking, telemetry or hardcoded credentials.

Open an issue with the steps to reproduce a bug and the way you deployed kobser. Report security problems privately as described in [SECURITY.md](SECURITY.md).

By contributing, you agree that your contributions are licensed under the [GPL-3.0](LICENSE).
