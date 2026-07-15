---
name: frontend-verification
description: "Standard frontend verification workflow: build, lint, and type-check Vue/TypeScript projects"
---

# Frontend Verification Skill

Standard verification workflow for Vue 3 + TypeScript + Vite frontend projects.

## When to Use

- After completing frontend code changes
- Before committing or pushing code
- When debugging build errors
- As part of code review process

## Workflow

### Step 1: Build Verification
```bash
cd "D:\CodeDemo\AssetManagementProgram\vue-assetmanagement"
npx vite build 2>&1 | Select-String "Build failed|✓|error during|modules transformed" | ForEach-Object { $_.Line.Trim() }
```

**Expected Output:**
- Success: `✓ built in X.XXs`
- Failure: Error messages with file locations

### Step 2: ESLint Check
```bash
cd "D:\CodeDemo\AssetManagementProgram\vue-assetmanagement"
npx eslint "src/**/*.vue" "src/**/*.ts" 2>&1
```

**Expected Output:**
- Success: No output (clean)
- Failure: Error messages with file locations and line numbers

### Step 3: TypeScript Compilation Check
```bash
cd "D:\CodeDemo\AssetManagementProgram\vue-assetmanagement"
npx vue-tsc --noEmit 2>&1
```

**Expected Output:**
- Success: No output (clean)
- Failure: TypeScript error messages

## Error Handling

### Build Errors
1. **Parse errors**: Check for syntax issues in Vue templates or TypeScript code
2. **Module not found**: Check import paths and dependencies
3. **Type errors**: Fix TypeScript type mismatches

### ESLint Errors
1. **Unused variables**: Remove or prefix with underscore
2. **Import errors**: Fix import paths or add to eslint ignore
3. **Vue template errors**: Check for invalid HTML/Vue syntax

### TypeScript Errors
1. **Type mismatches**: Fix type definitions or add proper types
2. **Missing imports**: Add missing imports
3. **Strict mode violations**: Add proper type annotations

## Integration with AGENTS.md

This workflow aligns with:
- **CT-1**: Core business logic must have test coverage
- **CT-5**: Test failures block commits
- **DR-5**: File/function size limits (500 lines)
- **DR-6**: Call chain depth limits

## Notes

- Always run all three checks for complete verification
- Fix errors in order: Build → ESLint → TypeScript
- Some ESLint errors from `.agents/skills/impeccable/` can be ignored (third-party code)
- For complex errors, check build output first to identify root cause