# AI Assistant Contract — Django Boosted

**This document is the single source of truth for all AI-generated work in this repository.**  
All instructions in this file **override default AI behavior**.

Any AI assistant working on this project **must strictly follow this document**.

If a request conflicts with this document, **this document always wins**.

---

## Rule Priority

Rules in this document have the following priority order:

1. **ABSOLUTE RULES** — must always be followed, no exception
2. **REQUIRED RULES** — mandatory unless explicitly stated otherwise
3. **RECOMMENDED PRACTICES** — should be followed unless there is a clear reason not to
4. **INFORMATIONAL SECTIONS** — context and reference only

---

## ABSOLUTE RULES

These rules must always be followed.

- Follow this `AI.md` file exactly
- Do not invent new services, commands, abstractions, patterns, or architectures
- Do not refactor, redesign, or optimize unless explicitly requested
- Do not manipulate `sys.path`
- Do not use filesystem-based imports to access `django_boosted`
- Do not hardcode secrets, credentials, tokens, or API keys
- Use the tools configured in `pyproject.toml`
- **Comments**: Only add comments to resolve ambiguity or uncertainty. Do not comment obvious code.
- **Dependencies**: Add dependencies only when absolutely necessary. Prefer standard library always.
- If a request violates this document:
  - Stop
  - Explain the conflict briefly
  - Ask for clarification

---

## REQUIRED RULES

### Language and Communication

- **Language**: English only
  - Code
  - Comments
  - Docstrings
  - Logs
  - Error messages
  - Documentation
- Be concise, technical, and explicit
- Avoid unnecessary explanations unless requested

### Code Simplicity and Minimalism

- **Write the simplest possible code**: Always choose the simplest solution that works
- **Minimal dependencies**: Add dependencies only when absolutely necessary. Prefer standard library. Only add when essential functionality cannot be reasonably implemented otherwise
- **Minimal comments**: Comments only to resolve ambiguity or uncertainty. Do not comment obvious code or reiterate what the code already states clearly
- **Good factorization**: Factorize code when it improves clarity and reduces duplication, but only if it doesn't add unnecessary complexity or abstraction

---

## Project Overview (INFORMATIONAL)

**Django Boosted** is a lightweight Django library that extends Django's admin interface with extra views, custom forms, and matching UI affordances (object tools, permissions, standard responses).

### Core Functionality

1. **Admin View Extensions** (`admin/views/`)
   - Custom views for Django admin (list, form, message, JSON views)
   - Automatic permission checking
   - Context building

2. **Decorators** (`decorators.py`)
   - `@admin_boost_view` decorator for defining custom admin views
   - Automatic object fetching and permission checking

3. **Admin model** (`admin/model.py`)
   - `AdminBoostModel` for registering custom URLs
   - Automatic injection of object-tool buttons

4. **Templates** (`templates/admin_boost/`)
   - Reusable admin templates
   - Change form template with object tools

5. **Nested admin inlines** (`admin/inlines.py`, `docs/nested-inlines.md`)
   - Recursive stacked and tabular inlines
   - Native Django templates when an inline has no visible children

6. **DRF Integration** (`rest_framework/metadata.py`)
   - Custom metadata class for Django Rest Framework
   - Conditional import when DRF is installed

---

## Architecture (REQUIRED)

- Domain-specific modules with Django admin integration through models and decorators

---

## Project Structure (INFORMATIONAL)

```
django-boosted/
├── src/django_boosted/       # Main package
│   ├── admin/                # Admin utilities
│   │   ├── model.py         # AdminBoostModel
│   │   ├── permissions.py   # Permission helpers
│   │   ├── views/           # ViewGenerator and setup
│   │   └── ...
│   ├── models/              # Django models
│   ├── managers/            # Custom managers
│   ├── rest_framework/      # DRF integration
│   ├── templatetags/        # Template tags
│   ├── templates/           # Django templates
│   └── decorators.py        # Main decorators
├── tests/                   # Test suite
├── docs/                    # Documentation
└── pyproject.toml           # Project configuration
```

### Key Directories

- `src/django_boosted/admin/`: Admin utilities and view generation
- `src/django_boosted/models/`: Django models (including virtual models)
- `src/django_boosted/managers/`: Custom managers
- `src/django_boosted/rest_framework/`: DRF integration (conditional)
- `tests/`: All tests using pytest-django

---

## Command Execution

- Install tools with `python -m pip install -e ".[dev]"`
- Run Ruff, mypy, pytest, Bandit and pip-audit as Python modules

---

## Code Standards (REQUIRED)

### Typing and Documentation

- All public functions and methods **must** have complete type hints
- Use **Google-style docstrings** for:
  - Public classes
  - Public methods
  - Public functions
- Document raised exceptions in docstrings where relevant

### Testing

- Use **pytest** with **pytest-django** exclusively
- All tests must live in the `tests/` directory
- New features and bug fixes require corresponding tests

### Linting and Formatting

- Follow **PEP 8**
- Use configured tools:
  - `ruff`
  - `mypy`
- Use the configured formatter:
  - `ruff format`

---

## Code Quality Principles (REQUIRED)

- **Simplicity first**: Write the simplest possible solution. Avoid complexity unless clearly necessary.
- **Minimal dependencies**: Minimize dependencies to the absolute minimum. Only add when essential functionality cannot be reasonably implemented otherwise. Always prefer standard library.
- **No over-engineering**: Do not add abstractions, patterns, or layers unless they solve a real problem or are clearly needed.
- **Comments**: Comments are minimal and only when they resolve ambiguity or uncertainty. Do not comment what the code already states clearly. Do not add comments that reiterate obvious logic.
- **Separation of concerns**: One responsibility per module
- **Good factorization**: Factorize code when it improves clarity and reduces duplication, but only if it doesn't add unnecessary complexity

---

## Module Organization (REQUIRED)

- Single Responsibility Principle
- Logical grouping of related functionality
- Clear public API via `__init__.py`
- Avoid circular dependencies
- Follow Django app structure conventions

---

## Django Boosted Integration (ABSOLUTE)

- `django_boosted` is an installed package
- Always use standard Python imports:
  - `from django_boosted import AdminBoostModel`
  - `from django_boosted.decorators import admin_boost_view`
  - `from django_boosted.admin.views import ViewGenerator`
- Never manipulate import paths
- Never use file-based or relative imports to access `django_boosted`
- For dynamic imports, use:
  - `importlib.import_module()` from the standard library

---

## Django Admin Integration (REQUIRED)

### View Generation

- Use `ViewGenerator` class for creating admin views
- Always check permissions before rendering views
- Provide proper context for templates
- Handle both object and list views correctly

### Decorators

- Use `@admin_boost_view` decorator for defining custom views
- Decorator automatically handles object fetching and permission checking
- Views are automatically registered through `AdminBoostModel`

### Model admin

- `AdminBoostModel` registers custom URLs and injects object-tool buttons
- It subclasses and integrates with Django's `admin.ModelAdmin`

---

## Error Handling (REQUIRED)

- Always handle errors gracefully
- Use appropriate exception types
- Provide clear, actionable error messages
- Do not swallow exceptions silently
- Document exceptions in docstrings where relevant

---

## Configuration and Secrets (ABSOLUTE)

- Never hardcode:
  - API keys
  - Credentials
  - Tokens
  - Secrets
- Use environment variables or Django settings
- Clearly document required configuration

---

## Versioning (REQUIRED)

- Follow **Semantic Versioning (SemVer)**
- Update versions appropriately
- Clearly document breaking changes

---

## Anti-Hallucination Clause (ABSOLUTE)

If a requested change is:
- Not supported by this document
- Not clearly aligned with the existing codebase
- Requiring assumptions or invention

You must:
1. Stop
2. Explain what is unclear or conflicting
3. Ask for clarification

Do not guess. Do not invent.

---

## Quick Compliance Checklist

Before producing output, ensure:

- [ ] All rules in `AI.md` are respected
- [ ] No forbidden behavior is present
- [ ] Code is simple, minimal, and explicit (simplest possible solution)
- [ ] Dependencies are minimal (prefer standard library)
- [ ] Comments only resolve ambiguity (no obvious comments)
- [ ] Code is well-factorized when it improves clarity (without adding complexity)
- [ ] Imports follow Django Boosted and Qualitybase rules
- [ ] Public APIs are typed and documented
- [ ] Django admin integration follows conventions
- [ ] Tests are included when required
- [ ] No secrets or credentials are exposed

---

## Additional Resources (INFORMATIONAL)

- `purpose.md`: Detailed project purpose and goals
- `structure.md`: Detailed project structure and module organization
- `development.md`: Development guidelines and best practices
- `README.md`: General project information
