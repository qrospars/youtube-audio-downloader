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
