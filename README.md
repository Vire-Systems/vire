# Vire Core

> Core build orchestration engine for Vire.

Vire Core is responsible for:

- Accepting validated build requests.
- Validating project configuration (`vire.toml`).
- Registering build metadata.
- Scheduling queued builds.
- Launching isolated build workers.
- Cleaning up abandoned workers.

---

# Architecture

```text
                Build Request
                      │
                      ▼
               FastAPI API Layer
                      │
                      ▼
             SQLite Build Database
                      │
                      ▼
                 Scheduler Loop
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
   Worker Launcher          Garbage Collector
        │
        ▼
   Docker Build Worker
        │
        ▼
   Build Artifacts
```

---

# Components

## API Layer

The API layer is implemented using **FastAPI**.

Responsibilities:

- Accept build requests.
- Validate the repository's `vire.toml`.
- Register build metadata.
- Register build state.
- Queue builds.

The API layer **never performs builds itself**.

---

## Scheduler

The scheduler continuously monitors queued builds.

Responsibilities:

- Determine available worker capacity.
- Read queued jobs.
- Dispatch workers asynchronously.
- Track running builds.

Workers are launched only when capacity is available.

---

## Worker

A worker is an isolated build environment.

Responsibilities:

- Clone the repository.
- Checkout the requested commit.
- Validate project configuration.
- Install dependencies (if required).
- Execute the build.
- Produce build artifacts.

Workers run inside Docker containers.

Container names are derived from the Job UUID.

---

## Garbage Collector

The garbage collector (GC) periodically scans Docker for Vire-managed containers.

Responsibilities:

- Detect stale workers.
- Remove abandoned containers.
- Prevent orphaned build environments.

Containers are identified using Docker labels.

---

# Build Configuration

Every supported repository contains a `vire.toml`.

Example:

```toml
[details]
framework = "vite"
package_manager = "npm"

[project]
framework_version = "22"
output_dir = "dist"
dependencies = true
```

Current fields:

| Field | Description |
|--------|-------------|
| framework | Framework used for the project |
| package_manager | Package manager |
| framework_version | Runtime version |
| output_dir | Directory containing build artifacts |
| dependencies | Whether dependency installation is required |

> The configuration format is still evolving.

---

# Database

Vire Core currently uses SQLite.

Two tables exist.

## BuildData

Stores immutable build metadata.

```text
job_uuid
user_uuid
remote_link
commit_id
repo_name
framework
package_manager
install_required
output_directory
```

---

## BuildState

Tracks build lifecycle.

```text
job_uuid
user_uuid
status
created_at
finished_at
error
```

Typical statuses:

- queued
- validating
- running
- passed
- failed
- terminated

---

# Design Goals

- Stateless workers
- Fully asynchronous scheduling
- Container isolation
- Simple architecture
- Horizontal scalability
- Clear separation of responsibilities

---

# Tech Stack

- Python 3.14+
- FastAPI
- SQLAlchemy
- SQLite
- Docker
- Redis (runtime state)
- PostgreSQL (for central state, in the future)

---

# Repository Structure

```text
Vire/
├── api/
├── core/
├── models/
├── objects/
├── tests/
├── utils/
└── application.py
```

> Folder names may change as the project evolves.

---

# Development Status

Vire Core is currently under active development.

Breaking changes to internal APIs, scheduler behaviour, worker lifecycle, and configuration formats should be expected until the first stable release.
