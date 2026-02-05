# Git Branching Strategy

This project uses Git Flow branching model:

## Main Branches
- **main** - Production-ready code. Merge here, then create a git tag to trigger releases.
- **develop** - Integration branch for features. Builds but does not release.

## Supporting Branches
- **feature/\*** - New features. Branch from `develop`, merge back to `develop`
  - Example: `feature/playlist-support`
- **hotfix/\*** - Quick fixes for production issues. Branch from `main`, merge back to `main` and `develop`
  - Example: `hotfix/crash-fix`
- **release/\*** - Release preparation. Branch from `develop`, merge to `main` when ready
  - Example: `release/v1.0`

## Workflow

### Adding a Feature
```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
# ... make changes ...
git push origin feature/my-feature
# Create Pull Request to develop
```

### Making a Hotfix
```bash
git checkout main
git pull origin main
git checkout -b hotfix/my-fix
# ... make changes ...
git push origin hotfix/my-fix
# Create Pull Request to main
```

### Releasing
1. Merge PR from `develop` → `main`
2. Create a git tag with semantic version:
   ```bash
   git checkout main
   git pull origin main
   git tag -a v1.1.0 -m "Release v1.1.0"
   git push origin v1.1.0
   ```
3. GitHub Actions automatically:
   - Builds Windows `.exe`
   - Builds macOS `.dmg`
   - Generates changelog from commits since last tag
   - Creates GitHub Release matching the tag name
4. Users download from [Releases](../../releases) page

**Version Format:** Use semantic versioning (v1.0.0, v1.0.1, v1.1.0, v2.0.0)

## Commit Message Format
For better changelog generation, use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Build/dependency changes

Example: `feat: add batch download support`

## Semantic Versioning Guide

Version format: `vMAJOR.MINOR.PATCH`

- **MAJOR** (v2.0.0) - Breaking changes. Users' existing workflows break. Example: Removing a feature, changing how downloads are organized
- **MINOR** (v1.1.0) - New features added. Backward compatible. Example: Adding playlist filtering, new audio quality options
- **PATCH** (v1.0.1) - Bug fixes only. No new features. Example: Fixing a crash, improving stability

## Real-World Example: Feature Tomorrow

### Scenario: Tomorrow you add a "Concurrent Download Limit" feature

#### Step 1: Create a feature branch
```bash
git checkout develop
git pull origin develop
git checkout -b feature/concurrent-limit
```

#### Step 2: Make changes and commit
```bash
# Edit youtube_mp3_downloader.pyw with your new feature
# Use conventional commit format:
git add youtube_mp3_downloader.pyw
git commit -m "feat: add concurrent download limit setting"

# Add/update tests:
git add tests/
git commit -m "test: add concurrent limit tests"

# If you update README:
git add README.md
git commit -m "docs: document concurrent limit setting"
```

#### Step 3: Push and create PR
```bash
git push origin feature/concurrent-limit
# Create PR from GitHub UI: `feature/concurrent-limit` → `develop`
```

#### Step 4: After PR is merged to develop
```bash
# Current state: develop has your feature
# Now you want to release it
git checkout main
git pull origin main
```

#### Step 5: Merge develop into main
```bash
# Option A: Via GitHub UI - Create PR from develop → main, then merge
# Option B: Via command line:
git merge --no-ff develop -m "Merge develop into main for release"
git push origin main
```

#### Step 6: Create the release tag
Since you added a **new feature** (backward compatible), increment **MINOR**:
```bash
# Current version: v1.0.0
# New version: v1.1.0 (new feature = minor bump)
git tag -a v1.1.0 -m "Release v1.1.0: Add concurrent download limit"
git push origin v1.1.0
```

#### Step 7: GitHub Actions handles the rest
- Workflow triggers automatically (detects `v1.1.0` tag)
- Builds Windows `.exe` and macOS `.dmg`
- Creates release on GitHub with changelog automatically generated from commits:
  ```
  Release v1.1.0
  
  ## Changes
  - feat: add concurrent download limit setting
  - test: add concurrent limit tests
  - docs: document concurrent limit setting
  ```
- Users see it on the [Releases](../../releases) page

### Other Scenarios

#### Bug fix for current version (PATCH)
```bash
# Current: v1.1.0
# User reports a crash
git checkout -b hotfix/crash-fix
# ... fix the crash ...
git push origin hotfix/crash-fix
# Create PR to main, merge, then:
git tag -a v1.1.1 -m "Release v1.1.1: Fix crash on invalid URLs"
git push origin v1.1.1
```

#### Multiple features with breaking changes (MAJOR)
```bash
# You've accumulated these features on develop:
# - Complete UI redesign
# - New settings location (old settings incompatible)
# - Removed support for Python 3.8
# This requires MAJOR version bump because users' existing setups break

git checkout main
git pull origin main
git merge --no-ff develop -m "Merge develop for major version"
git tag -a v2.0.0 -m "Release v2.0.0: Redesigned UI, new settings format"
git push origin v2.0.0
```

#### Multiple patches (cumulative)
```bash
# v1.1.0 is out, you fix several small issues on develop
# Merge to main and release as v1.1.1 (one patch covers all)
git checkout main
git merge develop
git tag -a v1.1.1 -m "Release v1.1.1: Multiple stability fixes"
git push origin v1.1.1
```

### Quick Decision Tree

When deciding which number to increment:

```
Did you make BREAKING CHANGES?
├─ YES → Increment MAJOR (v1.0.0 → v2.0.0)
└─ NO → Did you add new features (backward compatible)?
    ├─ YES → Increment MINOR (v1.0.0 → v1.1.0)
    └─ NO → Increment PATCH (v1.0.0 → v1.0.1)
```
