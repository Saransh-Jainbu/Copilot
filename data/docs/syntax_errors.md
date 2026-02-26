# Syntax Errors in CI/CD Pipelines

## Python SyntaxError: invalid syntax

**Root Cause**: Python code has a syntax mistake that prevents parsing. Common causes:
- Missing colons after `if`, `for`, `def`, `class` statements
- Mismatched parentheses, brackets, or quotes
- Using Python 3 syntax in a Python 2 environment (or vice versa)
- F-strings (`f"..."`) used in Python < 3.6
- Walrus operator (`:=`) used in Python < 3.8
- Match/case statements used in Python < 3.10

**Fix**:
1. Look at the line number and the `^` caret in the error — it points to where Python got confused. The actual error is often on the PREVIOUS line.
2. Check for missing closing brackets/parentheses on the line before.
3. Verify your CI Python version matches the syntax features you're using.
4. Use a linter locally before committing: `python -m py_compile file.py` or `ruff check .`

---

## Python IndentationError: unexpected indent / expected an indented block

**Root Cause**: Python uses whitespace for block structure. Mixing tabs and spaces, or inconsistent indentation, causes this error.

**Fix**:
1. Configure your editor to use spaces (4 spaces per indent level is PEP 8 standard).
2. Run `python -m tabnanny file.py` to detect mixed tabs/spaces.
3. In CI, add a linting step: `ruff check --select E1 src/` to catch indentation issues.
4. Many editors have "Convert Indentation to Spaces" commands.

---

## JavaScript/TypeScript: Unexpected token / Parse error

**Root Cause**: The JS/TS code has syntax that the parser doesn't understand. Common causes:
- Using optional chaining (`?.`) or nullish coalescing (`??`) with an old Node.js version
- JSX syntax in a `.js` file without proper Babel/TypeScript configuration
- Missing semicolons (in strict mode)
- TypeScript syntax in a `.js` file

**Fix**:
1. Check the exact line and column number in the error.
2. Ensure your Node.js version supports the syntax features you're using. Node 14+ supports most modern JS.
3. For TypeScript errors, ensure `tsconfig.json` has the correct `target` and `module` settings.
4. For JSX in `.js` files, either rename to `.jsx`/`.tsx` or configure your bundler to handle JSX in `.js` files.
5. Run `npx tsc --noEmit` locally to catch TypeScript errors before pushing.

---

## TypeScript TS1005: ';' expected / TS2304: Cannot find name

**Root Cause**: TypeScript compilation errors. TS1005 is usually a syntax issue (unclosed JSX tag, missing bracket). TS2304 means a type or variable isn't imported or declared.

**Fix**:
1. For TS1005: Check for unclosed JSX tags — every `<Component>` needs a `</Component>` or self-close `<Component />`.
2. For TS2304: Add the missing import or install the type definitions: `npm install --save-dev @types/<package>`.
3. Check `tsconfig.json` — ensure `jsx` is set to `react-jsx` for React projects.
4. Ensure `strictNullChecks` isn't causing unexpected type errors.

---

## YAML / JSON syntax errors in CI config

**Root Cause**: CI/CD configuration files (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Dockerfile`) have syntax errors. YAML is especially sensitive to indentation.

**Fix**:
1. Validate YAML before pushing: `python -c "import yaml; yaml.safe_load(open('file.yml'))"` or use an online YAML validator.
2. Common YAML mistakes: using tabs (YAML requires spaces), incorrect list indentation, unquoted strings with special characters (`:`, `#`, `{`, `}`).
3. For JSON: use `python -m json.tool file.json` to validate.
4. Install a YAML linter: `pip install yamllint && yamllint .github/workflows/`
