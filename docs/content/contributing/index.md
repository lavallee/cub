---
title: Contributing
description: How to contribute to Cub - from bug reports and documentation to new harnesses and task backends.
---

# Contributing to Cub

Thank you for your interest in contributing to Cub! This guide will help you get started, whether you're fixing a bug, improving documentation, or adding a new feature.

## Ways to Contribute

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### Report Bugs

Found something broken? [Open an issue](https://github.com/lavallee/cub/issues/new) with steps to reproduce.

</div>

<div class="feature-card" markdown>

#### Improve Documentation

Spotted a typo or unclear explanation? Documentation improvements are always welcome.

</div>

<div class="feature-card" markdown>

#### Add Features

Have an idea? Check the [roadmap](roadmap.md) or propose a new feature in discussions.

</div>

<div class="feature-card" markdown>

#### Build Integrations

Create new [harnesses](harnesses.md) or [task backends](backends.md) to extend Cub's capabilities.

</div>

</div>

---

## Quick Start

Ready to dive in? Here's how to get started:

```bash
# Fork and clone the repository
git clone https://github.com/YOUR-USERNAME/cub.git
cd cub

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev]"

# Run tests to verify setup
pytest tests/ -v
```

See the [Development Setup](setup.md) guide for detailed instructions.

---

## Contribution Areas

| Area | Guide | Difficulty |
|------|-------|------------|
| Bug fixes | Fix issues and submit PRs | Beginner |
| Documentation | Improve docs and examples | Beginner |
| Test coverage | Add missing tests | Beginner |
| New harness | Add AI coding assistant support | Intermediate |
| New backend | Add task storage system | Intermediate |
| Core features | Implement roadmap items | Advanced |

---

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and constructive in discussions
- Focus on the code, not the person
- Help others learn and grow
- Report unacceptable behavior to the maintainers

---

## Getting Help

<div class="grid cards" markdown>

-   :material-github: **GitHub Issues**

    ---

    For bugs and feature requests.

    [:octicons-arrow-right-24: Open an Issue](https://github.com/lavallee/cub/issues)

-   :material-message-question: **Discussions**

    ---

    For questions and ideas.

    [:octicons-arrow-right-24: Start a Discussion](https://github.com/lavallee/cub/discussions)

</div>

---

## Documentation Sections

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### [Architecture](architecture.md)

Understand Cub's hybrid Python/Bash architecture and module structure.

</div>

<div class="feature-card" markdown>

#### [Development Setup](setup.md)

Set up your development environment with all required tools.

</div>

<div class="feature-card" markdown>

#### [Adding Harnesses](harnesses.md)

Learn how to add support for new AI coding assistants.

</div>

<div class="feature-card" markdown>

#### [Adding Backends](backends.md)

Create new task storage backends for different systems.

</div>

<div class="feature-card" markdown>

#### [Roadmap](roadmap.md)

See planned features and how to propose new ones.

</div>

</div>
