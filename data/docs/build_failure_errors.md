# Build Failure Errors in CI/CD

## Docker build failed: RUN command returned non-zero code

**Root Cause**: A command inside the Dockerfile failed during `docker build`. The most common culprits:
- `pip install` or `npm install` failing due to missing packages or network issues
- `apt-get install` failing because package index is outdated
- Compilation errors in C/C++ extensions
- Missing system dependencies for Python packages (e.g., `psycopg2` needs `libpq-dev`)

**Fix**:
1. Always update package lists before installing: `RUN apt-get update && apt-get install -y <packages>`
2. Combine RUN commands to reduce layers and improve caching.
3. For Python packages with C extensions, install build dependencies:
```dockerfile
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && pip install --no-cache-dir -r requirements.txt
```
4. Use multi-stage builds to keep final image small:
```dockerfile
FROM python:3.11 AS builder
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
```

---

## make: *** Error / Compilation failed

**Root Cause**: The C/C++ build system (make, cmake, gcc) encountered errors. Usually:
- Missing header files or libraries
- Undefined references (linker errors) — forgot to link a library
- Syntax errors in C/C++ code
- Wrong compiler version or flags

**Fix**:
1. Install missing dev packages: `apt-get install -y build-essential libssl-dev`
2. For linker errors (`undefined reference`), add the library flag: `-lm` for math, `-lpthread` for threads.
3. Check compiler version: `gcc --version`. Some code requires GCC 9+ or Clang.
4. Read the FULL error — the first error is usually the root cause; subsequent errors are often cascading failures.

---

## Webpack / Vite / esbuild: Build failed with errors

**Root Cause**: Frontend bundler failed to compile the project. Common causes:
- TypeScript type errors
- Missing or moved imports
- CSS/SCSS syntax errors
- Unsupported browser targets in Babel config

**Fix**:
1. Run the build locally first: `npm run build` should reproduce the error.
2. For TypeScript errors, run `npx tsc --noEmit` to see all type errors.
3. Check that all imports resolve: missing files show as `Module not found` errors.
4. For CSS issues, validate SCSS syntax and check for undefined variables or mixins.
5. Update bundler and plugins to compatible versions.

---

## Gradle / Maven: Build failed

**Root Cause**: Java/Kotlin build tool failed. Common causes:
- Dependency resolution failure (artifact not found in repositories)
- Compilation errors in Java/Kotlin code
- Test failures (Gradle/Maven run tests during build by default)
- Plugin version incompatibility

**Fix**:
1. For missing artifacts: check repository URLs in `build.gradle` or `pom.xml`. Ensure Maven Central or your private repo is listed.
2. For compilation errors: fix the Java code. Run `gradle compileJava` or `mvn compile` locally.
3. To skip tests during build (temporary): `gradle build -x test` or `mvn package -DskipTests`.
4. Clear caches: `rm -rf ~/.gradle/caches` or `rm -rf ~/.m2/repository`.

---

## GitHub Actions: The process completed with exit code 1 / 2 / 127

**Root Cause**: A generic failure indicator from GitHub Actions.
- Exit code 1: General error (command failed)
- Exit code 2: Misuse of shell command (bad syntax, missing file)
- Exit code 127: Command not found (tool not installed in CI environment)

**Fix**:
1. For exit code 127: Install the required tool. Common fix:
```yaml
- name: Install tools
  run: |
    sudo apt-get update
    sudo apt-get install -y <tool-name>
```
2. For exit code 1: Look at the output ABOVE the error line — the actual failure message is earlier in the log.
3. For exit code 2: Check shell syntax. GitHub Actions uses `bash` by default on Linux, `pwsh` on Windows.
4. Add `set -e` at the top of multi-line run commands to fail fast on the first error.
