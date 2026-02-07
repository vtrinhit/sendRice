"""
Webhook Service
Handles sending notifications via n8n webhook.
"""
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import uuid

from app.config import settings
from app.schemas.send import WebhookResponse, SendResponse


class WebhookService:
    """Service for n8n webhook operations."""

    def __init__(self, webhook_url: Optional[str] = None, timeout: int = 30):
        """Initialize webhook service."""
        self.webhook_url = webhook_url or settings.n8n_webhook_url
        self.timeout = timeout
        self.retry_count = 3
        self.retry_delay = 1  # seconds

    def is_configured(self) -> bool:
        """Check if webhook is configured."""
        return bool(self.webhook_url)

    async def send_notification(
        self,
        phone: str,
        name: str,
        salary: int,
        image_base64: str,
        content: str = "",
    ) -> WebhookResponse:
        """
        Send salary notification to a single employee.

        Args:
            phone: Employee phone number (Zalo)
            name: Employee name
            salary: Salary amount
            image_base64: Base64 encoded salary image
            content: Message content/caption for the notification

        Returns:
            WebhookResponse with status and message
        """
        if not self.is_configured():
            return WebhookResponse(
                status="failed",
                message="Webhook URL not configured"
            )

        # Send base64 image directly in payload
        payload = {
            "sdt": phone,
            "ten": name,
            "luong": salary,
            "hinhanh": image_base64,  # Base64 image data
            "content": content
        }

        last_error = None

        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )

                    if response.status_code == 200:
                        # Parse response
                        try:
                            data = response.json()
                            return WebhookResponse(
                                status=data.get("status", "success"),
                                message=data.get("message")
                            )
                        except Exception:
                            # Assume success if 200 but no JSON
                            return WebhookResponse(status="success")
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"

            except httpx.TimeoutException:
                last_error = f"Request timeout after {self.timeout}s"
            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            # Wait before retry
            if attempt < self.retry_count - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return WebhookResponse(
            status="failed",
            message=last_error
        )

    async def send_batch(
        self,
        employees: List[Dict[str, Any]],
        content: str = "",
        concurrency: int = 5
    ) -> List[SendResponse]:
        """
        Send notifications to multiple employees.

        Args:
            employees: List of employee data dicts with phone, name, salary, image_url
            content: Message content/caption for all notifications
            concurrency: Maximum concurrent requests

        Returns:
            List of SendResponse for each employee
        """
        results = []
        semaphore = asyncio.Semaphore(concurrency)

        async def send_one(employee: Dict[str, Any]) -> SendResponse:
            async with semaphore:
                employee_id = employee.get("id")

                # Validate required fields
                if not employee.get("phone"):
                    return SendResponse(
                        employee_id=employee_id,
                        status="failed",
                        message="Missing phone number"
                    )

                if not employee.get("image_base64"):
                    return SendResponse(
                        employee_id=employee_id,
                        status="failed",
                        message="Salary image not generated"
                    )

                response = await self.send_notification(
                    phone=employee["phone"],
                    name=employee["name"],
                    salary=employee.get("salary", 0),
                    image_base64=employee["image_base64"],
                    content=content
                )

                return SendResponse(
                    employee_id=employee_id,
                    status=response.status,
                    message=response.message
                )

        # Run all sends concurrently with semaphore limiting
        tasks = [send_one(emp) for emp in employees]
        results = await asyncio.gather(*tasks)

        return list(results)

    async def test_webhook(self) -> WebhookResponse:
        """Test webhook connectivity with a dummy payload."""
        if not self.is_configured():
            return WebhookResponse(
                status="failed",
                message="Webhook URL not configured"
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Just test connectivity, don't send actual data
                response = await client.get(self.webhook_url)
                return WebhookResponse(
                    status="success",
                    message=f"Webhook reachable (HTTP {response.status_code})"
                )
        except Exception as e:
            return WebhookResponse(
                status="failed",
                message=f"Cannot reach webhook: {str(e)}"
            )


# Factory function to create webhook service with custom URL
def get_webhook_service(webhook_url: Optional[str] = None) -> WebhookService:
    """Get a webhook service instance."""
    return WebhookService(webhook_url=webhook_url)


# Default singleton instance
webhook_service = WebhookService()
