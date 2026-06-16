# Phase 32 — Asynchronous Workflow Execution

Target release: `v1.25.0` (Tentative)
Status: **In progress**
Goal: Refactor the workflow execution model from synchronous to asynchronous using a task queue (Celery) to support long-running 3D CFD simulations and large parametric studies.

---

## 1. Architectural Analysis

This phase introduces a fundamental change to the execution model, decoupling the API from the workflow runner.

- **Task Queue**: Celery will be introduced as the task queue, with Redis as the message broker. This is a standard, robust combination for asynchronous task processing in Python. A new `aerosynthx.task_queue` module will be created to configure the Celery application instance.
- **Task Refactoring**: The core execution logic currently inside `Pipeline.run`, `StudyRunner.run`, and `OptimizationRunner.run` will be extracted and wrapped in `@celery.task` decorators. The existing `run` methods will be converted into thin wrappers that simply call `.delay()` on the Celery tasks, submitting them to the queue and returning immediately.
- **API Behavior Change**:
  - The `POST` endpoints for creating runs, studies, and optimizations will now return a `202-Accepted` status code immediately, along with the ID of the created resource. They will no longer block until the analysis is complete.
  - Clients will use the existing `GET` endpoints (e.g., `GET /api/v1/runs/{run_id}`) to poll for the status of the job. The `status` field in the database (`running`, `completed`, `failed`) will be the source of truth.
- **Celery Worker**: A new CLI command, `aerosynthx worker`, will be added to start the Celery worker process. This process will listen to the Redis queue and execute the analysis tasks. This requires a new dependency on `celery` and `redis`.

This architecture allows the API server to remain lightweight and responsive, while the heavy computational work is handled by one or more separate worker processes, which can be scaled independently.

---

## 2. Goals & Constraints

- **Goal**: Decouple long-running analysis jobs from the synchronous API request/response cycle.
- **Goal**: Enable the execution of 3D CFD runs that may take hours to complete without timing out the API client.
- **Goal**: Provide a scalable foundation where multiple worker processes can consume jobs from the queue in parallel.
- **Constraint**: The user experience should be clear. The API should immediately return a job ID, and the status should be queryable.
- **Constraint**: The existing synchronous execution path should be preserved for local testing and simple workflows if possible, or a clear migration path provided. For this phase, we will fully transition to the async model.

---

## 3. Implementation Plan

1.  **Dependencies**: Add `celery` and `redis` to `pyproject.toml`.
2.  **`aerosynthx.task_queue`**:
    *   Create `celery.py` to define and configure the Celery app instance, pointing it to the Redis broker.
3.  **Refactor `pipeline.py`**:
    *   Create a new `_execute_run_task` function decorated with `@celery.task`. This function will contain the core logic from the current `_execute_run` method.
    *   Modify the public `Pipeline.run` method to simply call `_execute_run_task.delay(...)` and return a placeholder or initial `RunResult`.
4.  **Refactor `study/runner.py` and `optimizer/runner.py`**:
    *   Similarly, wrap the core logic of `StudyRunner.run` and `OptimizationRunner.run` in Celery tasks.
    *   The `run` methods will now submit the task and create the initial `StudyRow` or `OptimizationRow` in the database with a "queued" or "running" status.
5.  **API (`api/app.py`)**:
    *   Update the `POST` endpoints for runs, studies, and optimizations to return `202 Accepted`. The response body will contain the ID of the created job.
6.  **CLI (`workflow/cli.py`)**:
    *   Add a new `aerosynthx worker` command that invokes `celery -A aerosynthx.task_queue.celery_app worker`.
    *   The existing `run`, `study`, and `optimize` commands will now return immediately after submitting the job. A polling mechanism or a "follow" flag could be added to stream logs.

---

## 4. Acceptance Criteria

- [ ] `celery` and `redis` are added as project dependencies.
- [ ] A `celery.py` configuration module is created.
- [ ] The `Pipeline`, `StudyRunner`, and `OptimizationRunner` are refactored to use Celery tasks.
- [ ] The API `POST` endpoints return a `202 Accepted` status immediately.
- [ ] A new `aerosynthx worker` CLI command successfully starts a Celery worker.
- [ ] An end-to-end test demonstrates that a run submitted via the API is successfully executed by the Celery worker and the final status is correctly updated in the database.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   The Celery tasks will be tested in "eager" mode (`task_always_eager = True`), which executes them locally without needing a broker. This allows for testing the task logic itself.
    *   The refactored `run` methods will be tested to ensure they correctly call `.delay()` on the tasks with the right arguments.
- **Integration Tests**:
    *   The API tests for the `POST` endpoints will be updated to assert a `202` status code and to then poll the corresponding `GET` endpoint until the status changes to `completed` or `failed`.
- **Manual/End-to-End**: This phase requires manual testing of the full system: running the Redis server, starting the API server, starting the Celery worker, submitting a job via the API, and verifying that the worker picks it up and executes it.

---

## 6. Risks & Limitations

- **Infrastructure Complexity**: This phase introduces two new infrastructure components (Celery and Redis), which adds complexity to local development setup and deployment. The documentation must be very clear.
- **Error Handling**: Failures within Celery tasks (e.g., a worker crashing) need to be handled gracefully. The database status should be updated to "failed" in these cases.
- **Result Retrieval**: The current API design requires the client to poll for results. For a more advanced user experience, WebSockets could be used to push status updates to the client in real-time (this is a future extension).

---

## 7. Future Extensibility

- **Scalability**: With Celery in place, the system can be scaled horizontally by simply running more worker processes, even across multiple machines.
- **Task Routing**: Celery's routing capabilities can be used to send different types of jobs to different queues or workers (e.g., sending GPU-intensive tasks to workers on GPU-equipped machines).
- **Real-time Progress**: The foundation is now in place to build a real-time progress update system using WebSockets, where the Celery task can push events back to the API server and out to the client.
