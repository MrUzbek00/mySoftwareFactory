# Repository Analysis Reference

Efficient repository inspection starts broad, narrows quickly, and follows
evidence. The goal is not to summarize every file. The goal is to collect enough
task-relevant context to plan a safe change.

## Core Inspection Principles

- Start broad with root files, manifests, and directory shape.
- Narrow quickly using task terms, target paths, symbols, routes, and tests.
- Follow call paths from public entrypoints toward implementation details.
- Inspect tests to understand expected behavior and local test style.
- Inspect configuration when behavior may be controlled by settings or flags.
- Inspect nearby Git history when it explains why relevant code is shaped a
  certain way.
- Do not load unrelated modules to create a false sense of completeness.

## Python

High-value files often include:

- `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements*.txt`, `uv.lock`, or
  `poetry.lock`
- package entrypoints and console scripts
- `tests/`, `conftest.py`, and fixtures
- framework-specific settings modules

Look for package boundaries, service modules, serializers, clients, database
models, and test fixtures that match the task language.

## Django

High-value files often include:

- `manage.py`
- project `settings.py` and URL configuration
- app `models.py`, `views.py`, `serializers.py`, `forms.py`, and `admin.py`
- `migrations/`
- API route declarations
- tests under app directories or a shared `tests/` tree

Follow the path from URL routing to views, serializers, models, permissions, and
tests. Database migrations and compatibility with existing requests are often
important planning constraints.

## FastAPI

High-value files often include:

- the application factory or `FastAPI()` instance
- router modules
- Pydantic models and schemas
- dependency injection modules
- persistence or service layers
- API tests and OpenAPI-related configuration

Trace from route registration to request models, authorization dependencies,
service functions, and response contracts.

## Node.js

High-value files often include:

- `package.json`, lockfiles, and workspace manifests
- `tsconfig.json`, build configuration, and lint/test configuration
- application entrypoints
- route/controller modules
- service modules
- tests and fixtures

Identify whether the project is JavaScript or TypeScript, whether it uses a
workspace layout, and which scripts define test and validation behavior.

## React

High-value files often include:

- `package.json`
- `src/main.*`, `src/index.*`, or framework entrypoints
- route declarations
- component directories
- state management, hooks, and data client modules
- component and integration tests

Follow user-visible behavior from route or page components into data loading,
state updates, and API calls.

## Next.js

High-value files often include:

- `next.config.*`
- `app/` or `pages/`
- route handlers and API routes
- server actions
- shared components
- data access modules
- middleware and authentication configuration

Identify whether the app uses the App Router or Pages Router before planning
changes. Public route behavior and server/client boundaries are common risks.

## Generic Repositories

When the stack is unclear, inspect:

- root README and agent guidance
- manifests and lockfiles
- CI workflows
- Makefiles or task runners
- Docker files
- top-level directory names
- tests and examples

Use the smallest set of files that explains where the requested behavior lives,
which contracts are exposed, and which tests should guard the change.
