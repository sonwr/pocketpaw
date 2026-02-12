# Deep Work Dependency Scheduler
# Created: 2026-02-12
# Watches task completions and auto-dispatches ready tasks in dependency order.
#
# Key features:
# - get_ready_tasks: finds tasks with all blockers satisfied
# - on_task_completed: auto-dispatches newly unblocked tasks
# - validate_graph: cycle detection via Kahn's algorithm (works with Task and TaskSpec)
# - get_execution_order: groups tasks by dependency level (works with Task and TaskSpec)

import logging
from collections import deque

from pocketclaw.mission_control.models import Task, TaskStatus, now_iso

logger = logging.getLogger(__name__)


def _get_id(item) -> str:
    """Extract the identifier from a Task (.id) or TaskSpec (.key)."""
    if hasattr(item, "key") and item.key:
        return item.key
    return item.id


def _get_deps(item) -> list[str]:
    """Extract dependency list from a Task (.blocked_by) or TaskSpec (.blocked_by_keys)."""
    if hasattr(item, "blocked_by_keys"):
        return item.blocked_by_keys
    return item.blocked_by


class DependencyScheduler:
    """Schedules and dispatches tasks based on dependency order.

    The scheduler does NOT subscribe to bus events itself. The session layer
    is responsible for wiring on_task_completed to the appropriate bus events.
    """

    def __init__(self, manager, executor, human_router=None):
        """Initialize the scheduler.

        Args:
            manager: MissionControlManager instance (list_tasks, get_task, etc.)
            executor: MCTaskExecutor instance (execute_task_background)
            human_router: Optional human notification router (notify_human_task, notify_review_task)
        """
        self.manager = manager
        self.executor = executor
        self.human_router = human_router

    async def get_ready_tasks(self, project_id: str) -> list[Task]:
        """Return tasks in project where all blockers are satisfied.

        A task is "ready" when:
        - Its status is INBOX or ASSIGNED (not yet started)
        - All task IDs in its blocked_by list have status DONE

        Args:
            project_id: Project to check

        Returns:
            List of tasks ready to be dispatched
        """
        all_tasks = await self.manager.list_tasks()
        project_tasks = [t for t in all_tasks if t.project_id == project_id]
        done_ids = {t.id for t in project_tasks if t.status == TaskStatus.DONE}

        ready = []
        for task in project_tasks:
            if task.status not in (TaskStatus.INBOX, TaskStatus.ASSIGNED):
                continue
            if not task.blocked_by or all(bid in done_ids for bid in task.blocked_by):
                ready.append(task)
        return ready

    async def on_task_completed(self, task_id: str):
        """Called when a task finishes. Dispatch newly unblocked tasks.

        Args:
            task_id: ID of the task that just completed
        """
        task = await self.manager.get_task(task_id)
        if not task or not task.project_id:
            return

        ready = await self.get_ready_tasks(task.project_id)
        for ready_task in ready:
            await self._dispatch_task(ready_task)

        # Check if entire project is now complete
        await self.check_project_completion(task.project_id)

    async def _dispatch_task(self, task: Task):
        """Dispatch a single task based on its type.

        - agent tasks: sent to executor with first assignee
        - human tasks: routed to human_router.notify_human_task
        - review tasks: routed to human_router.notify_review_task

        Args:
            task: Task to dispatch
        """
        if task.task_type == "agent":
            agent_id = task.assignee_ids[0] if task.assignee_ids else None
            if agent_id:
                logger.info(f"Auto-dispatching agent task: {task.title}")
                await self.executor.execute_task_background(task.id, agent_id)
            else:
                logger.warning(f"Agent task has no assignee: {task.title}")
        elif task.task_type == "human":
            if self.human_router:
                logger.info(f"Routing human task: {task.title}")
                await self.human_router.notify_human_task(task)
            else:
                logger.warning(f"Human task but no router: {task.title}")
        elif task.task_type == "review":
            if self.human_router:
                logger.info(f"Routing review task: {task.title}")
                await self.human_router.notify_review_task(task)

    async def check_project_completion(self, project_id: str) -> bool:
        """Check if ALL tasks in project are DONE. If yes, mark project COMPLETED.

        Args:
            project_id: Project to check

        Returns:
            True if project is now completed
        """
        all_tasks = await self.manager.list_tasks()
        project_tasks = [t for t in all_tasks if t.project_id == project_id]

        if not project_tasks:
            return False

        all_done = all(t.status == TaskStatus.DONE for t in project_tasks)
        if all_done:
            project = await self.manager.get_project(project_id)
            if project:
                from pocketclaw.deep_work.models import ProjectStatus

                project.status = ProjectStatus.COMPLETED
                project.completed_at = now_iso()
                await self.manager.update_project(project)
                logger.info(f"Project completed: {project.title}")
            return True
        return False

    @staticmethod
    def validate_graph(tasks: list) -> tuple[bool, str]:
        """Validate dependency graph for cycles and missing references.

        Uses Kahn's algorithm for topological sort. If any nodes remain
        after processing, the graph contains a cycle.

        Works with both TaskSpec (.key/.blocked_by_keys) and Task (.id/.blocked_by).

        Args:
            tasks: List of Task or TaskSpec objects

        Returns:
            (is_valid, error_message) tuple. error_message is empty if valid.
        """
        if not tasks:
            return True, ""

        # Build lookup of all known IDs
        all_ids = {_get_id(t) for t in tasks}

        # Check for references to non-existent tasks
        for task in tasks:
            for dep in _get_deps(task):
                if dep not in all_ids:
                    return False, f"Task '{_get_id(task)}' depends on non-existent task '{dep}'"

        # Kahn's algorithm: compute in-degree and adjacency
        in_degree: dict[str, int] = {_get_id(t): 0 for t in tasks}
        # adjacency: dep -> list of tasks that depend on it
        adjacency: dict[str, list[str]] = {_get_id(t): [] for t in tasks}

        for task in tasks:
            tid = _get_id(task)
            deps = _get_deps(task)
            in_degree[tid] = len(deps)
            for dep in deps:
                adjacency[dep].append(tid)

        # Start with zero in-degree nodes
        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        processed = 0

        while queue:
            node = queue.popleft()
            processed += 1
            for dependent in adjacency[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if processed < len(tasks):
            # Find nodes still in the cycle for error message
            cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
            return False, f"Dependency cycle detected involving: {', '.join(sorted(cycle_nodes))}"

        return True, ""

    @staticmethod
    def get_execution_order(tasks: list) -> list[list[str]]:
        """Group tasks by dependency level for parallel execution.

        Level 0: tasks with no dependencies
        Level 1: tasks depending only on level 0 tasks
        Level N: tasks depending on level N-1 or lower

        Works with both TaskSpec (.key/.blocked_by_keys) and Task (.id/.blocked_by).

        Args:
            tasks: List of Task or TaskSpec objects

        Returns:
            List of lists, each inner list is a set of task IDs/keys
            that can execute in parallel at that level.
        """
        if not tasks:
            return []

        # Build maps
        task_map = {_get_id(t): t for t in tasks}
        all_ids = set(task_map.keys())

        # Compute levels via BFS (Kahn's algorithm variant)
        in_degree: dict[str, int] = {}
        adjacency: dict[str, list[str]] = {tid: [] for tid in all_ids}

        for task in tasks:
            tid = _get_id(task)
            deps = [d for d in _get_deps(task) if d in all_ids]
            in_degree[tid] = len(deps)
            for dep in deps:
                adjacency[dep].append(tid)

        # Current level starts with zero in-degree
        current_level = [tid for tid, deg in in_degree.items() if deg == 0]
        levels: list[list[str]] = []

        while current_level:
            levels.append(sorted(current_level))
            next_level = []
            for node in current_level:
                for dependent in adjacency[node]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level.append(dependent)
            current_level = next_level

        return levels
