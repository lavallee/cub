"""
Service layer for cub.

Services are stateless orchestrators that compose domain operations into clean
API surfaces. Any interface (CLI, API, skills, future UIs) calls service methods
instead of reaching into core packages directly.

Design principles:
- Every user-facing action maps to a service method.
- Methods accept typed inputs, return typed outputs, raise typed exceptions.
- No Rich, no sys.exit, no print statements—presentation is the caller's job.
- Services are created via factory methods that accept configuration.

Modules:
    run: RunService wraps core/run/ to provide run loop orchestration.
"""

from cub.core.services.run import RunService

__all__ = [
    "RunService",
]
