# Releasing

To publish a new version to PyPI:

1. Update `version` in `pyproject.toml`
2. Add a release entry to `CHANGELOG.md`
3. Commit, tag, and push:
   ```
   git tag v1.1.0
   git push origin v1.1.0
   ```

The `publish.yml` workflow builds, tests, and uploads to PyPI automatically on version tags.
