# Test Failure Errors in CI/CD

## pytest: FAILED — AssertionError

**Root Cause**: A test assertion failed — the actual output didn't match the expected result. This means either:
- The code has a bug introduced by recent changes
- The test expectations are outdated after a valid code change
- The test depends on external state (database, API, file system) that differs in CI

**Fix**:
1. Read the assertion message: `assert X == Y` tells you exactly what was expected vs. what was returned.
2. Run the failing test locally: `pytest tests/test_file.py::test_name -v`
3. If the code change was intentional, update the test expectations.
4. For flaky tests that sometimes pass, look for:
   - Race conditions in async code
   - Hardcoded timestamps or dates
   - Tests depending on execution order
5. Use `pytest --tb=long` for full tracebacks in CI.

---

## pytest: FAILED — fixture not found / setup error

**Root Cause**: A test fixture is missing, misconfigured, or has an error in its setup. Common causes:
- Fixture defined in a different `conftest.py` that isn't being loaded
- Fixture has a dependency that fails (e.g., database connection)
- Circular fixture dependencies

**Fix**:
1. Check `conftest.py` files — fixtures are scoped by directory. Ensure the fixture is in the right `conftest.py`.
2. Run with `pytest --fixtures` to see all available fixtures.
3. For database fixtures, ensure the test database is set up in CI (use SQLite for tests or a service container).
4. Use `@pytest.fixture(autouse=True)` carefully — it runs for ALL tests in scope.

---

## Jest / Mocha: Test suite failed to run

**Root Cause**: JavaScript test runner couldn't even start executing tests. Common causes:
- Import/require errors — module not found
- Syntax errors in test files
- Missing test configuration (jest.config.js, .babelrc)
- TypeScript compilation errors in test files

**Fix**:
1. Check the error before "Test suite failed" — it usually shows an import or syntax error.
2. Ensure `jest.config.js` has correct `transform` and `moduleNameMapper` settings.
3. For TypeScript tests: install `ts-jest` and configure transform:
```js
transform: { "^.+\\.tsx?$": "ts-jest" }
```
4. For React component tests: install and configure `@testing-library/react` and the correct Jest environment (`jsdom`).

---

## Test timeout — tests running too long in CI

**Root Cause**: Tests that pass locally timeout in CI because:
- CI machines are slower (shared resources, fewer CPUs)
- Network-dependent tests can't reach external services
- Database operations are slower without SSD
- Memory-intensive tests hit CI memory limits

**Fix**:
1. Increase timeout for slow tests: `@pytest.mark.timeout(60)` or Jest's `jest.setTimeout(30000)`.
2. Mock external services instead of calling them: use `unittest.mock`, `responses`, or `nock`.
3. Run slow tests separately: `pytest -m "not slow"` for fast CI, full suite on nightly.
4. Parallelize: `pytest -n auto` (with `pytest-xdist`) or Jest's `--maxWorkers`.

---

## Test failures due to missing test data / fixtures

**Root Cause**: Tests expect data files, database state, or API responses that aren't available in CI.

**Fix**:
1. Include test fixtures in the repository: `tests/fixtures/` directory with sample data.
2. Use factory functions or builders to create test data programmatically.
3. For database tests, use migrations + seed data in CI setup.
4. For API tests, record real responses with `vcrpy` (Python) or `nock` (Node.js) and replay them.
5. Never depend on production data — always use deterministic test data.

---

## Code coverage below threshold

**Root Cause**: CI is configured to fail if code coverage drops below a minimum (e.g., 80%). New code without tests triggers this.

**Fix**:
1. Write tests for the new code — focus on the uncovered lines shown in the coverage report.
2. Run `pytest --cov=src --cov-report=html` locally to see exactly which lines need tests.
3. If the threshold is too aggressive, adjust it gradually. Don't disable it entirely.
4. Exclude generated code, migrations, and config files from coverage: add to `.coveragerc` or `pyproject.toml`.
