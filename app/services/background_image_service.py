"""
Background Image Generation Service
Handles batch image generation with real-time SSE updates.
OPTIMIZED: Processes all employees in single batch to reduce LibreOffice overhead.
"""
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

from sqlalchemy import update

from app.database import async_session_maker
from app.models import Employee
from app.services.salary_slip_service_optimized import (
    OptimizedSalarySlipService,
    BatchResult
)

logger = logging.getLogger(__name__)


@dataclass
class ImageTask:
    """Represents an image generation task."""
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    status: str = "pending"  # pending, processing, completed, failed
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SessionProgress:
    """Tracks progress for a session's image generation."""
    session_id: uuid.UUID
    total: int = 0
    completed: int = 0
    failed: int = 0
    processing: int = 0
    tasks: Dict[str, ImageTask] = field(default_factory=dict)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    is_running: bool = False


class BackgroundImageService:
    """
    Service for background image generation with real-time updates.

    OPTIMIZED VERSION:
    - Processes all employees in a single batch
    - Opens Excel file only once
    - LibreOffice starts only once per batch
    - Real-time progress updates via SSE
    """

    def __init__(self, max_workers: int = 1):
        """
        Initialize the service.

        Args:
            max_workers: Number of concurrent batch processes.
                         Set to 1 since batch already processes sequentially.
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.sessions: Dict[str, SessionProgress] = {}
        self._lock = asyncio.Lock()

    async def start_generation(
        self,
        session_id: uuid.UUID,
        excel_file_path: str,
        employees: List[Dict[str, Any]],
        image_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start background image generation for all employees in a session.

        Args:
            session_id: Import session ID
            excel_file_path: Path to the Excel file
            employees: List of employee dicts with id, employee_code, name
            image_config: Image generation config

        Returns:
            Session ID as string for tracking
        """
        session_key = str(session_id)

        async with self._lock:
            # Create progress tracker
            progress = SessionProgress(
                session_id=session_id,
                total=len(employees)
            )

            for emp in employees:
                task = ImageTask(
                    employee_id=emp["id"],
                    employee_code=emp["employee_code"] or "",
                    employee_name=emp["name"]
                )
                progress.tasks[str(emp["id"])] = task

            self.sessions[session_key] = progress

        # Start background processing
        asyncio.create_task(
            self._process_batch(
                session_key,
                excel_file_path,
                employees,
                image_config or {}
            )
        )

        return session_key

    async def _process_batch(
        self,
        session_key: str,
        excel_file_path: str,
        employees: List[Dict[str, Any]],
        image_config: Dict[str, Any]
    ):
        """
        Process all employees in a single optimized batch.

        This is much faster than processing one by one because:
        - Excel file is opened only once
        - LibreOffice process stays alive during batch
        """
        progress = self.sessions.get(session_key)
        if not progress:
            return

        progress.is_running = True

        # Build employee code to ID mapping
        code_to_emp = {}
        for emp in employees:
            if emp.get("employee_code"):
                code_to_emp[emp["employee_code"]] = emp

        # Get list of valid employee codes
        valid_codes = [
            emp["employee_code"]
            for emp in employees
            if emp.get("employee_code")
        ]

        # Mark employees without code as failed immediately
        for emp in employees:
            if not emp.get("employee_code"):
                emp_id = str(emp["id"])
                task = progress.tasks.get(emp_id)
                if task:
                    task.status = "failed"
                    task.error = "Employee code is required"
                    progress.failed += 1

                    await self._update_employee_status(
                        emp["id"], "failed", "Employee code is required"
                    )
                    await self._notify_subscribers(session_key, {
                        "type": "status",
                        "employee_id": emp_id,
                        "status": "failed",
                        "name": task.employee_name,
                        "error": "Employee code is required"
                    })

        if not valid_codes:
            progress.is_running = False
            await self._notify_subscribers(session_key, {
                "type": "complete",
                "total": progress.total,
                "completed": progress.completed,
                "failed": progress.failed
            })
            return

        # Mark all valid employees as processing
        for code in valid_codes:
            emp = code_to_emp[code]
            emp_id = str(emp["id"])
            task = progress.tasks.get(emp_id)
            if task:
                task.status = "processing"
                progress.processing += 1

                await self._update_employee_status(emp["id"], "processing")
                await self._notify_subscribers(session_key, {
                    "type": "status",
                    "employee_id": emp_id,
                    "status": "processing",
                    "name": task.employee_name
                })

        # Create callback for real-time updates
        async def on_result(emp_code: str, result: BatchResult):
            emp = code_to_emp.get(emp_code)
            if not emp:
                return

            emp_id = str(emp["id"])
            task = progress.tasks.get(emp_id)
            if not task:
                return

            progress.processing -= 1

            if result.success:
                task.status = "completed"
                progress.completed += 1

                await self._save_image_result(
                    emp["id"],
                    f"data:image/png;base64,{result.base64_image}",
                    result.salary,
                    "completed"
                )

                await self._notify_subscribers(session_key, {
                    "type": "status",
                    "employee_id": emp_id,
                    "status": "completed",
                    "name": task.employee_name,
                    "has_image": True
                })
            else:
                task.status = "failed"
                task.error = result.error
                progress.failed += 1

                await self._update_employee_status(
                    emp["id"], "failed", result.error
                )

                await self._notify_subscribers(session_key, {
                    "type": "status",
                    "employee_id": emp_id,
                    "status": "failed",
                    "name": task.employee_name,
                    "error": result.error
                })

        # Run batch processing in executor
        loop = asyncio.get_event_loop()

        def run_batch_sync():
            """Synchronous batch processing with async callback bridge."""
            service = OptimizedSalarySlipService()

            def sync_callback(emp_code: str, result: BatchResult):
                # Schedule async callback on the event loop
                asyncio.run_coroutine_threadsafe(
                    on_result(emp_code, result),
                    loop
                )

            return service.generate_batch(
                excel_file_path,
                valid_codes,
                image_config,
                callback=sync_callback
            )

        try:
            await loop.run_in_executor(self.executor, run_batch_sync)
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Mark remaining as failed
            for code in valid_codes:
                emp = code_to_emp[code]
                emp_id = str(emp["id"])
                task = progress.tasks.get(emp_id)
                if task and task.status == "processing":
                    task.status = "failed"
                    task.error = str(e)
                    progress.processing -= 1
                    progress.failed += 1

                    await self._update_employee_status(
                        emp["id"], "failed", str(e)
                    )

        progress.is_running = False
        await self._notify_subscribers(session_key, {
            "type": "complete",
            "total": progress.total,
            "completed": progress.completed,
            "failed": progress.failed
        })

    async def _update_employee_status(
        self,
        employee_id: uuid.UUID,
        status: str,
        error: Optional[str] = None
    ):
        """Update employee image_status in database."""
        async with async_session_maker() as db:
            stmt = (
                update(Employee)
                .where(Employee.id == employee_id)
                .values(image_status=status, image_error=error)
            )
            await db.execute(stmt)
            await db.commit()

    async def _save_image_result(
        self,
        employee_id: uuid.UUID,
        image_url: str,
        salary: Optional[int],
        status: str
    ):
        """Save generated image to database."""
        async with async_session_maker() as db:
            values = {
                "salary_image_url": image_url,
                "image_status": status,
                "image_error": None
            }
            if salary is not None:
                values["salary"] = salary

            stmt = (
                update(Employee)
                .where(Employee.id == employee_id)
                .values(**values)
            )
            await db.execute(stmt)
            await db.commit()

    async def _notify_subscribers(self, session_key: str, data: Dict[str, Any]):
        """Send update to all SSE subscribers."""
        progress = self.sessions.get(session_key)
        if not progress:
            return

        # Add progress info
        data["progress"] = {
            "total": progress.total,
            "completed": progress.completed,
            "failed": progress.failed,
            "processing": progress.processing,
            "pending": progress.total - progress.completed - progress.failed - progress.processing
        }

        dead_queues = []
        for queue in progress.subscribers:
            try:
                await queue.put(data)
            except Exception:
                dead_queues.append(queue)

        # Remove dead subscribers
        for q in dead_queues:
            progress.subscribers.discard(q)

    async def subscribe(self, session_key: str) -> asyncio.Queue:
        """Subscribe to updates for a session."""
        queue: asyncio.Queue = asyncio.Queue()

        progress = self.sessions.get(session_key)
        if progress:
            progress.subscribers.add(queue)
            # Send current status immediately
            await queue.put({
                "type": "init",
                "progress": {
                    "total": progress.total,
                    "completed": progress.completed,
                    "failed": progress.failed,
                    "processing": progress.processing,
                    "pending": progress.total - progress.completed - progress.failed - progress.processing,
                    "is_running": progress.is_running
                }
            })

        return queue

    def unsubscribe(self, session_key: str, queue: asyncio.Queue):
        """Unsubscribe from updates."""
        progress = self.sessions.get(session_key)
        if progress:
            progress.subscribers.discard(queue)

    def get_progress(self, session_key: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a session."""
        progress = self.sessions.get(session_key)
        if not progress:
            return None

        return {
            "total": progress.total,
            "completed": progress.completed,
            "failed": progress.failed,
            "processing": progress.processing,
            "pending": progress.total - progress.completed - progress.failed - progress.processing,
            "is_running": progress.is_running
        }

    def cleanup_session(self, session_key: str):
        """Clean up session data."""
        if session_key in self.sessions:
            del self.sessions[session_key]


# Singleton instance
background_image_service = BackgroundImageService(max_workers=1)
