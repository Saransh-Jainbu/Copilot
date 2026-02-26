# Python Dependency Errors in CI/CD

## ModuleNotFoundError: No module named 'X'

**Root Cause**: The Python package is not installed in the CI/CD environment. This commonly happens when:
- The package is missing from `requirements.txt` or `setup.py`
- The package was added locally but never committed to version control
- The virtual environment in CI doesn't match your local environment

**Fix**:
1. Add the missing package to `requirements.txt`: `pip freeze > requirements.txt` or manually add the package name and version.
2. Ensure the CI pipeline runs `pip install -r requirements.txt` before executing any Python scripts.
3. If using `setup.py`, add the package to `install_requires`.
4. If using `pyproject.toml` with Poetry, run `poetry add <package>`.

**Example CI Fix (GitHub Actions)**:
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
```

---

## ImportError: cannot import name 'X' from 'Y'

**Root Cause**: The import exists but the specific name doesn't. This usually means:
- Version mismatch — the installed version doesn't have that function/class
- Circular imports in your own code
- The package API changed between versions

**Fix**:
1. Check the package version: `pip show <package>`. Compare with what you're importing.
2. Pin the correct version in `requirements.txt`: `package==1.2.3`.
3. Check the package changelog for breaking API changes.
4. For circular imports: restructure your code to avoid importing from modules that import from you.

---

## pip install fails with "Could not find a version that satisfies the requirement"

**Root Cause**: The specified version doesn't exist, or it's not compatible with your Python version. Common scenarios:
- Typo in the version number
- The package was yanked from PyPI
- The package doesn't have a wheel for your Python version or OS
- Using a Python version that's too new or too old for the package

**Fix**:
1. Check available versions: `pip index versions <package>` or visit https://pypi.org/project/<package>
2. Remove the exact version pin and use a compatible range: `package>=1.2,<2.0`
3. Ensure your CI Python version matches your development environment.
4. For packages with C extensions, ensure build tools are installed: `apt-get install build-essential python3-dev`

---

## pip install fails with "No matching distribution found"

**Root Cause**: Similar to above but often related to platform or Python version incompatibility.

**Fix**:
1. Verify the package supports your Python version and OS.
2. Try upgrading pip: `pip install --upgrade pip`
3. If behind a corporate proxy, configure pip: `pip install --proxy http://proxy:port <package>`
4. For private packages, ensure the index URL is configured: `pip install --index-url https://private.pypi.org/simple/ <package>`

---

## Requirements conflict / dependency resolution failure

**Root Cause**: Two or more packages require incompatible versions of the same dependency. pip's resolver cannot find a valid combination.

**Fix**:
1. Use `pip install --use-deprecated=legacy-resolver` as a temporary workaround.
2. Identify the conflict: `pip check` shows incompatible packages.
3. Update the conflicting packages to versions that share compatible dependencies.
4. Consider using `pip-tools` or `poetry` for better dependency resolution.
5. Use virtual environments to isolate project dependencies.
