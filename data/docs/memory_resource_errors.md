# Memory & Resource Errors in CI/CD

## OOMKilled / Container killed (exit code 137)

**Root Cause**: The process exceeded its memory limit and was killed by the kernel's OOM killer. In CI, this happens because CI runners have limited resources.

**Fix**:
1. **Docker**: increase the memory limit: `docker run -m 4g myapp`.
2. **Kubernetes**: increase `resources.limits.memory` in the Pod spec.
3. **GitHub Actions**: consider using larger runners (not available on free tier) or self-hosted runners with more memory.
4. **Optimize the build**: use smaller Docker base images, multi-stage builds, and avoid loading large files into memory.

---

## JavaScript heap out of memory / "FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed"

**Root Cause**: Node.js ran out of heap memory. Common during:
- Webpack/Vite builds with large codebases
- TypeScript compilation with many files
- `npm install` with massive `node_modules`

**Fix**:
1. Increase Node.js heap size:
```bash
export NODE_OPTIONS="--max-old-space-size=4096"  # 4 GB
```
2. In CI workflow:
```yaml
env:
  NODE_OPTIONS: "--max-old-space-size=4096"
```
3. For Webpack: use `Lazy compilation`, `SplitChunksPlugin`, or switch to Vite/esbuild.
4. For TypeScript: use `--incremental` compilation and `tsconfig.json` project references.

---

## Python MemoryError

**Root Cause**: Python process exceeded available memory. Common when:
- Loading large datasets entirely into memory
- Creating huge lists or data structures
- Memory leaks from long-running processes
- Processing large files without streaming

**Fix**:
1. Use generators and streaming instead of loading everything at once:
```python
# Bad: loads entire file into memory
data = open('huge.csv').readlines()
# Good: streams line by line
with open('huge.csv') as f:
    for line in f:
        process(line)
```
2. Use `pandas` with `chunksize` for large CSVs: `pd.read_csv('big.csv', chunksize=10000)`.
3. Use `del` and `gc.collect()` to free memory in loops.
4. Reduce the CI runner's parallelism to lower memory usage.

---

## Java OutOfMemoryError: Java heap space

**Root Cause**: The JVM ran out of heap memory. Common in builds (Gradle/Maven) and applications.

**Fix**:
1. Increase JVM heap:
```bash
export JAVA_OPTS="-Xmx2g -Xms512m"
export GRADLE_OPTS="-Xmx2g"
export MAVEN_OPTS="-Xmx2g"
```
2. In GitHub Actions:
```yaml
env:
  JAVA_OPTS: "-Xmx2g"
  GRADLE_OPTS: "-Dorg.gradle.jvmargs=-Xmx2g"
```
3. For Gradle: enable the Gradle Daemon with memory limits in `gradle.properties`:
```
org.gradle.jvmargs=-Xmx2g -XX:+HeapDumpOnOutOfMemoryError
```
4. Use incremental builds to reduce memory usage.

---

## "No space left on device" / Disk full in CI

**Root Cause**: The CI runner's disk is full. Common causes:
- Docker images/layers filling up disk space
- Large build artifacts or dependencies cached
- Log files growing unbounded
- Multiple builds on the same runner without cleanup

**Fix**:
1. Clean up Docker: `docker system prune -af` at the start of the job.
2. In GitHub Actions, free disk space:
```yaml
- name: Free disk space
  run: |
    sudo rm -rf /usr/share/dotnet
    sudo rm -rf /opt/ghc
    sudo rm -rf /usr/local/share/boost
    docker system prune -af
```
3. Use `.dockerignore` to exclude unnecessary files from the build context.
4. Clean up after tests: remove temporary files, test databases, coverage reports.
5. For self-hosted runners: set up periodic cleanup cron jobs.

---

## Process limit exceeded / "fork: retry: Resource temporarily unavailable"

**Root Cause**: The system hit the maximum number of processes or file descriptors. Common with:
- Parallel test runners spawning too many processes
- Fork bombs (accidental infinite recursion with process spawning)
- Too many concurrent Docker containers

**Fix**:
1. Limit parallel test workers: `pytest -n 2` instead of `pytest -n auto`.
2. Increase system limits in CI:
```bash
ulimit -n 65535  # File descriptors
ulimit -u 4096   # Max processes
```
3. For Docker: set PID limits: `docker run --pids-limit 100 myapp`.
4. Close file handles and connections properly in your code.
