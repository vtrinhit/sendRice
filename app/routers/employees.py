"""
Employees Router
Handles employee CRUD and sending operations.
"""
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Employee, SendHistory, ImportSession, AppSetting
from app.schemas.employee import EmployeeResponse, EmployeeUpdateRequest
from app.schemas.send import SendRequest, SendResponse, BatchSendRequest, BatchSendResponse
from app.services.image_generator import image_generator
from app.services.gdrive_service import gdrive_service
from app.services.webhook_service import webhook_service
from app.services.excel_parser import ExcelParserService
from app.config import settings


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    session_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List all employees, optionally filtered by session."""
    query = select(Employee).options(selectinload(Employee.send_history))

    if session_id:
        query = query.where(Employee.session_id == uuid.UUID(session_id))

    query = query.order_by(Employee.row_number)

    result = await db.execute(query)
    employees = result.scalars().all()

    return employees


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a single employee by ID."""
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.send_history))
        .where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return employee


@router.patch("/{employee_id}")
async def update_employee(
    employee_id: str,
    data: EmployeeUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update employee data."""
    result = await db.execute(
        select(Employee).where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)

    return {"status": "success", "employee": employee}


@router.post("/{employee_id}/generate-image")
async def generate_salary_image(
    employee_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Generate salary image for an employee."""
    # Get employee with session
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.session))
        .where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Get Excel config for image generation
    config_result = await db.execute(
        select(AppSetting).where(AppSetting.key == "excel_config")
    )
    config_setting = config_result.scalar_one_or_none()
    config = config_setting.value if config_setting else {}

    # Generate salary image
    employee_data = {
        "employee_code": employee.employee_code,
        "salary": employee.salary,
        "row_number": employee.row_number,
    }

    try:
        image_path = image_generator.generate_salary_image(
            employee_name=employee.name,
            employee_data=employee_data,
        )

        # Upload to Google Drive if configured
        if gdrive_service.is_configured():
            filename = f"salary_{employee.employee_code or employee.name}_{uuid.uuid4().hex[:8]}.png"
            file_id, image_url = gdrive_service.upload_file(
                file_path=image_path,
                filename=filename
            )

            # Update employee with image URL
            employee.salary_image_url = image_url
            await db.commit()

            # Clean up local file
            image_generator.cleanup_image(image_path)

            return {
                "status": "success",
                "image_url": image_url,
                "file_id": file_id
            }
        else:
            # Return local path (for development/preview)
            return {
                "status": "success",
                "image_path": image_path,
                "message": "Google Drive not configured, image stored locally"
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate image: {str(e)}"
        )


@router.post("/{employee_id}/send")
async def send_notification(
    employee_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Send salary notification to an employee."""
    # Get employee
    result = await db.execute(
        select(Employee).where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Validate required data
    if not employee.phone:
        raise HTTPException(
            status_code=400,
            detail="Employee has no phone number"
        )

    if not employee.salary_image_url:
        raise HTTPException(
            status_code=400,
            detail="Salary image not generated. Generate image first."
        )

    # Create send history record
    send_record = SendHistory(
        employee_id=employee.id,
        status="sending"
    )
    db.add(send_record)
    await db.commit()

    try:
        # Send via webhook
        response = await webhook_service.send_notification(
            phone=employee.phone,
            name=employee.name,
            salary=employee.salary or 0,
            image_url=employee.salary_image_url
        )

        # Update send history
        send_record.status = response.status
        send_record.webhook_response = {"status": response.status, "message": response.message}
        if response.status == "failed":
            send_record.error_message = response.message

        await db.commit()

        # Return HTMX partial if requested
        if request.headers.get("HX-Request"):
            await db.refresh(employee)
            return templates.TemplateResponse(
                "partials/employee_row.html",
                {
                    "request": request,
                    "employee": employee,
                    "send_status": response.status,
                }
            )

        return {
            "status": response.status,
            "message": response.message,
            "employee_id": str(employee.id)
        }

    except Exception as e:
        send_record.status = "failed"
        send_record.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send notification: {str(e)}"
        )


@router.post("/batch/generate-images")
async def batch_generate_images(
    data: BatchSendRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate salary images for multiple employees."""
    results = []

    for emp_id in data.employee_ids:
        try:
            result = await db.execute(
                select(Employee).where(Employee.id == emp_id)
            )
            employee = result.scalar_one_or_none()

            if not employee:
                results.append({
                    "employee_id": str(emp_id),
                    "status": "failed",
                    "message": "Employee not found"
                })
                continue

            # Generate image
            employee_data = {
                "employee_code": employee.employee_code,
                "salary": employee.salary,
                "row_number": employee.row_number,
            }

            image_path = image_generator.generate_salary_image(
                employee_name=employee.name,
                employee_data=employee_data,
            )

            # Upload to Google Drive
            if gdrive_service.is_configured():
                filename = f"salary_{employee.employee_code or employee.name}_{uuid.uuid4().hex[:8]}.png"
                file_id, image_url = gdrive_service.upload_file(
                    file_path=image_path,
                    filename=filename
                )
                employee.salary_image_url = image_url
                image_generator.cleanup_image(image_path)

                results.append({
                    "employee_id": str(emp_id),
                    "status": "success",
                    "image_url": image_url
                })
            else:
                results.append({
                    "employee_id": str(emp_id),
                    "status": "success",
                    "image_path": image_path,
                    "message": "Stored locally (Google Drive not configured)"
                })

        except Exception as e:
            results.append({
                "employee_id": str(emp_id),
                "status": "failed",
                "message": str(e)
            })

    await db.commit()

    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "total": len(data.employee_ids),
        "success": success_count,
        "failed": len(data.employee_ids) - success_count,
        "results": results
    }


@router.post("/batch/send")
async def batch_send_notifications(
    data: BatchSendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Send notifications to multiple employees."""
    # Get all employees
    result = await db.execute(
        select(Employee).where(Employee.id.in_(data.employee_ids))
    )
    employees = result.scalars().all()

    # Prepare employee data for batch send
    employees_data = []
    for emp in employees:
        employees_data.append({
            "id": emp.id,
            "phone": emp.phone,
            "name": emp.name,
            "salary": emp.salary,
            "salary_image_url": emp.salary_image_url,
        })

    # Send batch
    results = await webhook_service.send_batch(employees_data)

    # Create send history records
    for send_result in results:
        send_record = SendHistory(
            employee_id=send_result.employee_id,
            status=send_result.status,
            error_message=send_result.message if send_result.status == "failed" else None
        )
        db.add(send_record)

    await db.commit()

    success_count = sum(1 for r in results if r.status == "success")
    failed_count = len(results) - success_count

    # Return HTMX partial if requested
    if request.headers.get("HX-Request"):
        # Refresh employee list
        result = await db.execute(
            select(Employee)
            .options(selectinload(Employee.send_history))
            .where(Employee.id.in_(data.employee_ids))
            .order_by(Employee.row_number)
        )
        updated_employees = result.scalars().all()

        return templates.TemplateResponse(
            "partials/employee_table.html",
            {
                "request": request,
                "employees": updated_employees,
                "total_employees": len(updated_employees),
                "batch_result": {
                    "total": len(results),
                    "success": success_count,
                    "failed": failed_count
                }
            }
        )

    return BatchSendResponse(
        total=len(results),
        success=success_count,
        failed=failed_count,
        results=results
    )


@router.get("/{employee_id}/preview", response_class=HTMLResponse)
async def preview_salary_image(
    employee_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get a preview modal for employee salary image."""
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.send_history))
        .where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return templates.TemplateResponse(
        "partials/preview_modal.html",
        {
            "request": request,
            "employee": employee,
        }
    )
