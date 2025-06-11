.PHONY: install
install: ## Install the virtual environment and install the pre-commit hooks
	@echo "🚀 Creating virtual environment using uv"
	@uv sync
	@uv run pre-commit install

# Semantic Versioning with Commitizen
.PHONY: version-init
version-init: ## Initialize Commitizen configuration for semantic versioning
	@echo "🚀 Initializing Commitizen for semantic versioning"
	@uv add --group dev commitizen
	@uv run cz init

.PHONY: version-show
version-show: ## Show current project version
	@echo "🚀 Current project version:"
	@uv run cz version --project

.PHONY: version-bump
version-bump: ## Bump version automatically based on conventional commits
	@echo "🚀 Bumping version using semantic versioning"
	@uv run cz bump --changelog

.PHONY: version-bump-dry
version-bump-dry: ## Preview version bump without making changes
	@echo "🚀 Previewing version bump (dry run)"
	@uv run cz bump --dry-run

.PHONY: version-bump-patch
version-bump-patch: ## Force bump patch version (x.x.X)
	@echo "🚀 Bumping patch version"
	@uv run cz bump --increment PATCH --changelog

.PHONY: version-bump-minor
version-bump-minor: ## Force bump minor version (x.X.x)
	@echo "🚀 Bumping minor version"
	@uv run cz bump --increment MINOR --changelog

.PHONY: version-bump-major
version-bump-major: ## Force bump major version (X.x.x)
	@echo "🚀 Bumping major version"
	@uv run cz bump --increment MAJOR --changelog

.PHONY: commit
commit: ## Create a conventional commit using Commitizen
	@echo "🚀 Creating conventional commit"
	@uv run cz commit

.PHONY: changelog
changelog: ## Generate changelog from conventional commits
	@echo "🚀 Generating changelog"
	@uv run cz changelog

# GitHub Release Management
.PHONY: github-release
github-release: ## Create GitHub release from latest tag with changelog
	@echo "🚀 Creating GitHub release"
	@git push origin main --tags
	@gh release create $(shell git describe --tags --abbrev=0) --title "Release $(shell git describe --tags --abbrev=0)" --notes-from-tag

.PHONY: github-release-with-changelog
github-release-with-changelog: ## Create GitHub release with generated changelog
	@echo "🚀 Creating GitHub release with changelog"
	@git push origin main --tags
	@gh release create $(shell git describe --tags --abbrev=0) --title "Release $(shell git describe --tags --abbrev=0)" --notes-file CHANGELOG.md

.PHONY: release-full
release-full: check test version-bump build-and-publish github-release ## Complete release: check, test, bump, publish to PyPI, and create GitHub release
	@echo "🚀 Full release complete! Published to PyPI and GitHub."

.PHONY: release-dry
release-dry: check test version-bump-dry ## Dry run of full release process
	@echo "🚀 This would be released as version:"
	@uv run cz version --project

# Version Revert Commands
.PHONY: version-revert-local
version-revert-local: ## Revert local version bump (before push)
	@echo "🚀 Reverting local version bump"
	@git reset --hard HEAD~1
	@echo "✅ Local version bump reverted"

.PHONY: version-revert-with-tag
version-revert-with-tag: ## Revert version bump and remove tags (use with caution)
	@echo "🚀 Reverting version bump and removing tags"
	@read -p "Enter the tag to remove (e.g., v1.2.3): " tag && \
	git tag -d $$tag && \
	git push origin --delete $$tag && \
	git reset --hard HEAD~1 && \
	echo "✅ Version bump and tag $$tag reverted"

.PHONY: version-yank-pypi
version-yank-pypi: ## Yank a version from PyPI (makes it unavailable for new installs)
	@echo "🚀 Yanking version from PyPI"
	@read -p "Enter package name: " package && \
	read -p "Enter version to yank (e.g., 1.2.3): " version && \
	read -p "Enter reason: " reason && \
	uvx twine yank $$package $$version --reason "$$reason" && \
	echo "✅ Version $$version yanked from PyPI"

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Linting code: Running pre-commit"
	@uv run pre-commit run -a
	@echo "🚀 Static type checking: Running mypy"
	@uv run mypy
	@echo "🚀 Checking for obsolete dependencies: Running deptry"
	@uv run deptry .

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	@uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml
	@echo "🚀 Generating coverage badge"
	@uv run coverage-badge -f -o coverage.svg

.PHONY: build
build: clean-build ## Build wheel file
	@echo "🚀 Creating wheel file"
	@uvx --from build pyproject-build --installer uv

.PHONY: clean-build
clean-build: ## Clean build artifacts
	@echo "🚀 Removing build artifacts"
	@uv run python -c "import shutil; import os; shutil.rmtree('dist') if os.path.exists('dist') else None"

.PHONY: publish
publish: ## Publish a release to PyPI.
	@echo "🚀 Publishing."
	@uvx twine upload --repository-url https://upload.pypi.org/legacy/ dist/*

.PHONY: publish-test
publish-test: ## Publish to TestPyPI for testing
	@echo "🚀 Publishing to TestPyPI (test server)"
	@uvx twine upload --repository-url https://test.pypi.org/legacy/ dist/*

.PHONY: build-and-publish
build-and-publish: build publish ## Build and publish.

.PHONY: build-and-publish-test
build-and-publish-test: build publish-test ## Build and publish to TestPyPI for testing

.PHONY: test-install
test-install: ## Install package from TestPyPI to verify upload
	@echo "🚀 Installing from TestPyPI to test"
	@read -p "Enter package name: " package && \
	read -p "Enter version (or press enter for latest): " version && \
	if [ -z "$$version" ]; then \
		uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ $$package; \
	else \
		uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ $$package==$$version; \
	fi

.PHONY: docs-test
docs-test: ## Test if documentation can be built without warnings or errors
	@uv run mkdocs build -s

.PHONY: docs
docs: ## Build and serve the documentation
	@uv run mkdocs serve

.PHONY: help
help:
	@uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
