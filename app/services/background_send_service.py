"""
Background Send Service
Handles batch sending with delay and real-time SSE updates.
"""
import asyncio
import uuid
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Employee, SendHistory
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


@dataclass
class SendTask:
    """Represents a send task."""
    employee_id: uuid.UUID
    employee_name: str
    phone: str
    status: str = "pending"  # pending, sending, success, failed
    error: Optional[str] = None


@dataclass
class SendSessionProgress:
    """Tracks progress for a batch send session."""
    session_id: str
    total: int = 0
    sent: int = 0
    failed: int = 0
    pending: int = 0
    current_index: int = 0
    tasks: Dict[str, SendTask] = field(default_factory=dict)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    is_running: bool = False


class BackgroundSendService:
    """
    Service for background batch sending with real-time updates.
    Sends one by one with configurable delay between each send.
    """

    def __init__(self):
        self.sessions: Dict[str, SendSessionProgress] = {}
        self._lock = asyncio.Lock()

    async def start_batch_send(
        self,
        batch_id: str,
        employee_ids: List[uuid.UUID],
        webhook_config: Dict[str, Any],
        message_content: str = ""
    ) -> str:
        """
        Start background batch send for employees.

        Args:
            batch_id: Unique batch ID for tracking
            employee_ids: List of employee UUIDs to send
            webhook_config: Webhook configuration with send_delay
            message_content: Message content to send

        Returns:
            Batch ID for tracking
        """
        async with self._lock:
            progress = SendSessionProgress(
                session_id=batch_id,
                total=len(employee_ids),
                pending=len(employee_ids)
            )
            self.sessions[batch_id] = progress

        # Start background processing
        asyncio.create_task(
            self._process_batch(
                batch_id,
                employee_ids,
                webhook_config,
                message_content
            )
        )

        return batch_id

    async def _process_batch(
        self,
        batch_id: str,
        employee_ids: List[uuid.UUID],
        webhook_config: Dict[str, Any],
        message_content: str
    ):
        """Process batch sending one by one with delay."""
        progress = self.sessions.get(batch_id)
        if not progress:
            return

        progress.is_running = True

        # Get delay from config (default 3 seconds)
        send_delay = webhook_config.get("send_delay", 3)

        # Create webhook service with config
        webhook_service = WebhookService(
            webhook_url=webhook_config.get("webhook_url"),
            timeout=webhook_config.get("timeout", 30)
        )
        webhook_service.retry_count = webhook_config.get("retry_count", 3)

        # Fetch all employees with their data
        async with async_session_maker() as db:
            result = await db.execute(
                select(Employee)
                .where(Employee.id.in_(employee_ids))
            )
            employees = result.scalars().all()

        # Create task for each employee
        emp_map = {}
        for emp in employees:
            emp_id_str = str(emp.id)
            task = SendTask(
                employee_id=emp.id,
                employee_name=emp.name,
                phone=emp.phone or ""
            )
            progress.tasks[emp_id_str] = task
            emp_map[emp.id] = emp

        # Notify initial status
        await self._notify_subscribers(batch_id, {
            "type": "init",
            "total": progress.total,
            "pending": progress.pending
        })

        # Process each employee one by one
        for idx, emp_id in enumerate(employee_ids):
            emp = emp_map.get(emp_id)
            if not emp:
                continue

            emp_id_str = str(emp_id)
            task = progress.tasks.get(emp_id_str)
            if not task:
                continue

            progress.current_index = idx

            # Skip if no phone or no image
            if not emp.phone:
                task.status = "failed"
                task.error = "Không có số điện thoại"
                progress.pending -= 1
                progress.failed += 1

                await self._save_send_history(emp_id, "failed", "Không có số điện thoại")
                await self._notify_subscribers(batch_id, {
                    "type": "status",
                    "employee_id": emp_id_str,
                    "name": emp.name,
                    "status": "failed",
                    "error": "Không có số điện thoại",
                    "index": idx
                })
                continue

            if not emp.salary_image_url:
                task.status = "failed"
                task.error = "Chưa tạo ảnh lương"
                progress.pending -= 1
                progress.failed += 1

                await self._save_send_history(emp_id, "failed", "Chưa tạo ảnh lương")
                await self._notify_subscribers(batch_id, {
                    "type": "status",
                    "employee_id": emp_id_str,
                    "name": emp.name,
                    "status": "failed",
                    "error": "Chưa tạo ảnh lương",
                    "index": idx
                })
                continue

            # Mark as sending
            task.status = "sending"
            progress.pending -= 1

            await self._notify_subscribers(batch_id, {
                "type": "status",
                "employee_id": emp_id_str,
                "name": emp.name,
                "status": "sending",
                "index": idx
            })

            # Extract base64 from data URL
            image_data = emp.salary_image_url
            if image_data.startswith("data:image/png;base64,"):
                image_base64 = image_data.replace("data:image/png;base64,", "")
            else:
                image_base64 = image_data

            # Send via webhook
            try:
                response = await webhook_service.send_notification(
                    phone=emp.phone,
                    name=emp.name,
                    salary=emp.salary or 0,
                    image_base64=image_base64,
                    content=message_content
                )

                if response.status == "success":
                    task.status = "success"
                    progress.sent += 1
                    await self._save_send_history(emp_id, "success")
                else:
                    task.status = "failed"
                    task.error = response.message
                    progress.failed += 1
                    await self._save_send_history(emp_id, "failed", response.message)

            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                progress.failed += 1
                await self._save_send_history(emp_id, "failed", str(e))

            # Notify status update
            await self._notify_subscribers(batch_id, {
                "type": "status",
                "employee_id": emp_id_str,
                "name": emp.name,
                "status": task.status,
                "error": task.error,
                "index": idx
            })

            # Wait delay before next send (except for last one)
            if idx < len(employee_ids) - 1 and send_delay > 0:
                await asyncio.sleep(send_delay)

        # Mark complete
        progress.is_running = False
        await self._notify_subscribers(batch_id, {
            "type": "complete",
            "total": progress.total,
            "sent": progress.sent,
            "failed": progress.failed
        })

    async def _save_send_history(
        self,
        employee_id: uuid.UUID,
        status: str,
        error: Optional[str] = None
    ):
        """Save send history record."""
        async with async_session_maker() as db:
            record = SendHistory(
                employee_id=employee_id,
                status=status,
                error_message=error
            )
            db.add(record)
            await db.commit()

    async def _notify_subscribers(self, batch_id: str, data: Dict[str, Any]):
        """Send update to all SSE subscribers."""
        progress = self.sessions.get(batch_id)
        if not progress:
            return

        # Add progress info
        data["progress"] = {
            "total": progress.total,
            "sent": progress.sent,
            "failed": progress.failed,
            "pending": progress.pending,
            "is_running": progress.is_running
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

    async def subscribe(self, batch_id: str) -> asyncio.Queue:
        """Subscribe to updates for a batch."""
        queue: asyncio.Queue = asyncio.Queue()

        progress = self.sessions.get(batch_id)
        if progress:
            progress.subscribers.add(queue)
            # Send current status immediately
            await queue.put({
                "type": "init",
                "progress": {
                    "total": progress.total,
                    "sent": progress.sent,
                    "failed": progress.failed,
                    "pending": progress.pending,
                    "is_running": progress.is_running
                }
            })

        return queue

    def unsubscribe(self, batch_id: str, queue: asyncio.Queue):
        """Unsubscribe from updates."""
        progress = self.sessions.get(batch_id)
        if progress:
            progress.subscribers.discard(queue)

    def get_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a batch."""
        progress = self.sessions.get(batch_id)
        if not progress:
            return None

        return {
            "total": progress.total,
            "sent": progress.sent,
            "failed": progress.failed,
            "pending": progress.pending,
            "is_running": progress.is_running
        }

    def cleanup_batch(self, batch_id: str):
        """Clean up batch data."""
        if batch_id in self.sessions:
            del self.sessions[batch_id]


# Singleton instance
background_send_service = BackgroundSendService()
