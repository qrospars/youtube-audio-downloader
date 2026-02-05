# Git Branching Strategy

This project uses Git Flow branching model:

## Main Branches
- **main** - Production-ready code. Automatically creates releases when pushed to.
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
1. Create a PR from `develop` to `main`
2. Merge the PR
3. The CI/CD pipeline automatically:
   - Builds Windows `.exe`
   - Builds macOS `.dmg`
   - Generates changelog from commit messages
   - Creates a GitHub Release with both binaries

## Commit Message Format
For better changelog generation, use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Build/dependency changes

Example: `feat: add batch download support`
