---
name: backend-testing
description: "Standard backend testing workflow: run Django tests with pytest, check coverage, and verify migrations"
---

# Backend Testing Skill

Standard testing workflow for Django + DRF backend projects.

## When to Use

- After completing backend code changes
- Before committing or pushing code
- When debugging test failures
- As part of code review process
- When verifying database migrations

## Workflow

### Step 1: Run All Tests
```bash
cd "D:\CodeDemo\AssetManagementProgram\asset_management_backend"
pytest apps/ -v --tb=short 2>&1 | Select-String -Pattern "passed|failed|error" -Context 0,0
```

**Expected Output:**
- Success: `X passed in X.XXs`
- Failure: Failed test names and error messages

### Step 2: Run Specific App Tests
```bash
cd "D:\CodeDemo\AssetManagementProgram\asset_management_backend"
pytest apps/assetmanagement/tests/ -v --tb=short 2>&1
```

**Expected Output:**
- Success: All tests pass
- Failure: Specific test failures with details

### Step 3: Check Test Coverage
```bash
cd "D:\CodeDemo\AssetManagementProgram\asset_management_backend"
pytest --cov=. --cov-fail-under=80 --cov-report=html -v 2>&1
```

**Expected Output:**
- Success: Coverage report generated
- Failure: Coverage below 80% threshold

### Step 4: Verify Migrations
```bash
cd "D:\CodeDemo\AssetManagementProgram\asset_management_backend"
python manage.py makemigrations --dry-run 2>&1 | findstr "No changes detected"
python manage.py migrate --plan 2>&1
```

**Expected Output:**
- Success: No pending migrations
- Failure: Pending migrations detected

## Error Handling

### Test Failures
1. **Import errors**: Check module dependencies and paths
2. **Database errors**: Check database connection and migrations
3. **Assertion errors**: Fix test expectations or business logic
4. **Timeout errors**: Optimize slow queries or add indexes

### Migration Issues
1. **Missing migrations**: Run `python manage.py makemigrations`
2. **Migration conflicts**: Resolve with `python manage.py migrate --fake`
3. **Data loss warnings**: Review migration operations carefully

### Coverage Issues
1. **Low coverage**: Add tests for uncovered code paths
2. **Core module coverage**: Ensure Service/Store layers have 90%+ coverage
3. **Edge cases**: Add tests for error conditions and edge cases

## Integration with AGENTS.md

This workflow aligns with:
- **CT-1**: Core business logic must have test coverage
- **CT-2**: Coverage threshold ≥80% overall, ≥90% for core modules
- **CT-3**: State machine full path testing
- **CT-4**: Regression barrier - add tests after bug fixes
- **CT-5**: Test failures block commits
- **CT-6**: Migration safety verification
- **SC-3**: SQL injection protection (parameterized queries)

## Notes

- Always run all tests before committing
- Check coverage for core modules (Service/Store layers)
- Verify migrations with `--dry-run` and `--plan` before applying
- Use `-x` flag to stop on first failure for faster debugging
- Use `--tb=short` for concise error output