"""
Employees Router
Handles employee CRUD and sending operations.
"""
import asyncio
import os
import uuid
from typing import Dict, List, Optional
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
from app.services.salary_slip_service_optimized import optimized_salary_slip_service, OptimizedSalarySlipService
from app.services.webhook_service import webhook_service
from app.config import settings
from app.helpers import get_image_config


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
    """Generate salary image for an employee using Excel salary slip sheet."""
    # Get employee with session (need session.file_path)
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.session))
        .where(Employee.id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Check if Excel file exists
    if not employee.session or not employee.session.file_path:
        raise HTTPException(
            status_code=400,
            detail="Excel file not found. Please re-upload the file."
        )

    if not os.path.exists(employee.session.file_path):
        raise HTTPException(
            status_code=400,
            detail="Excel file has been deleted. Please re-upload."
        )

    # Check employee code is available
    if not employee.employee_code:
        raise HTTPException(
            status_code=400,
            detail="Employee code is required for image generation"
        )

    # Get image config from settings
    image_config = await get_image_config(db)

    try:
        # Generate salary slip image using LibreOffice
        base64_image, salary_from_excel = optimized_salary_slip_service.generate_single(
            excel_file_path=employee.session.file_path,
            employee_code=employee.employee_code,
            image_config=image_config
        )

        # Update employee with salary from E24 if available
        if salary_from_excel is not None:
            employee.salary = salary_from_excel

        # Store base64 image as data URL for preview
        employee.salary_image_url = f"data:image/png;base64,{base64_image}"
        await db.commit()

        return {
            "status": "success",
            "message": "Salary image generated successfully",
            "salary": salary_from_excel
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

    # Extract base64 from data URL if present
    image_data = employee.salary_image_url
    if image_data.startswith("data:image/png;base64,"):
        image_base64 = image_data.replace("data:image/png;base64,", "")
    else:
        image_base64 = image_data

    # Create send history record
    send_record = SendHistory(
        employee_id=employee.id,
        status="sending"
    )
    db.add(send_record)
    await db.commit()

    try:
        # Send via webhook with base64 image
        response = await webhook_service.send_notification(
            phone=employee.phone,
            name=employee.name,
            salary=employee.salary or 0,
            image_base64=image_base64
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
    """Generate salary images for multiple employees using batch processing."""
    # Get image config once
    image_config = await get_image_config(db)

    # Fetch all employees with their sessions in a single query
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.session))
        .where(Employee.id.in_(data.employee_ids))
    )
    employees = result.scalars().all()

    # Build employee lookup by ID
    emp_by_id = {emp.id: emp for emp in employees}

    # Track validation errors and group valid employees by Excel file
    validation_errors: List[Dict] = []
    employees_by_file: Dict[str, List[Employee]] = {}

    for emp_id in data.employee_ids:
        emp = emp_by_id.get(emp_id)

        if not emp:
            validation_errors.append({
                "employee_id": str(emp_id),
                "status": "failed",
                "message": "Employee not found"
            })
            continue

        if not emp.session or not emp.session.file_path:
            validation_errors.append({
                "employee_id": str(emp.id),
                "status": "failed",
                "message": "Excel file not found"
            })
            continue

        if not os.path.exists(emp.session.file_path):
            validation_errors.append({
                "employee_id": str(emp.id),
                "status": "failed",
                "message": "Excel file has been deleted"
            })
            continue

        if not emp.employee_code:
            validation_errors.append({
                "employee_id": str(emp.id),
                "status": "failed",
                "message": "Employee code is required"
            })
            continue

        # Group by file path for batch processing
        file_path = emp.session.file_path
        if file_path not in employees_by_file:
            employees_by_file[file_path] = []
        employees_by_file[file_path].append(emp)

    # Process each file group using batch generation
    results: List[Dict] = list(validation_errors)
    service = OptimizedSalarySlipService()

    for file_path, emps in employees_by_file.items():
        # Build code to employee mapping
        code_to_emp = {emp.employee_code: emp for emp in emps}
        employee_codes = list(code_to_emp.keys())

        try:
            # Run batch generation in executor (CPU-bound work)
            loop = asyncio.get_event_loop()
            batch_results = await loop.run_in_executor(
                None,
                lambda fp=file_path, codes=employee_codes, cfg=image_config: service.generate_batch(fp, codes, cfg)
            )

            # Process batch results
            for batch_result in batch_results:
                emp = code_to_emp.get(batch_result.employee_code)
                if not emp:
                    continue

                if batch_result.success:
                    emp.salary_image_url = f"data:image/png;base64,{batch_result.base64_image}"
                    if batch_result.salary is not None:
                        emp.salary = batch_result.salary
                    emp.image_status = "completed"
                    emp.image_error = None

                    results.append({
                        "employee_id": str(emp.id),
                        "status": "success",
                        "salary": batch_result.salary
                    })
                else:
                    emp.image_status = "failed"
                    emp.image_error = batch_result.error

                    results.append({
                        "employee_id": str(emp.id),
                        "status": "failed",
                        "message": batch_result.error
                    })

        except Exception as e:
            # Mark all employees in this batch as failed
            for emp in emps:
                emp.image_status = "failed"
                emp.image_error = str(e)
                results.append({
                    "employee_id": str(emp.id),
                    "status": "failed",
                    "message": str(e)
                })

    await db.commit()

    success_count = sum(1 for r in results if r.get("status") == "success")
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
        # Extract base64 from data URL
        image_base64 = None
        if emp.salary_image_url:
            if emp.salary_image_url.startswith("data:image/png;base64,"):
                image_base64 = emp.salary_image_url.replace("data:image/png;base64,", "")
            else:
                image_base64 = emp.salary_image_url

        employees_data.append({
            "id": emp.id,
            "phone": emp.phone,
            "name": emp.name,
            "salary": emp.salary,
            "image_base64": image_base64,
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
