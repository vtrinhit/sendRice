"""
Main Router
Handles the main page and Excel file upload.
"""
import os
import uuid
import shutil
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.config import settings
from app.models import ImportSession, Employee, AppSetting
from app.services.excel_parser import parse_excel_file, ExcelParserService
from app.services.background_image_service import background_image_service


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


async def get_excel_config(db: AsyncSession) -> dict:
    """Get Excel configuration from database or defaults."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "excel_config")
    )
    setting = result.scalar_one_or_none()

    if setting and setting.value:
        return setting.value

    # Return defaults
    return {
        "sheet_name": settings.default_sheet_name,
        "header_row": settings.default_header_row,
        "data_start_row": settings.default_data_start_row,
        "code_column": settings.default_code_column,
        "name_column": settings.default_name_column,
        "phone_column": settings.default_phone_column,
        "salary_column": settings.default_salary_column,
    }


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Render the main page."""
    # Get active session if any
    result = await db.execute(
        select(ImportSession)
        .where(ImportSession.status == "active")
        .order_by(desc(ImportSession.imported_at))
        .limit(1)
    )
    current_session = result.scalar_one_or_none()

    employees = []
    if current_session:
        emp_result = await db.execute(
            select(Employee)
            .where(Employee.session_id == current_session.id)
            .options(selectinload(Employee.send_history))
            .order_by(Employee.row_number)
        )
        employees = emp_result.scalars().all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "session": current_session,
            "employees": employees,
            "total_employees": len(employees),
        }
    )


@router.post("/upload")
async def upload_excel(
    request: Request,
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process an Excel file."""
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )

    # Save uploaded file
    upload_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}_{file.filename}")
    try:
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    try:
        # Get Excel configuration
        config = await get_excel_config(db)

        # Use form sheet_name if provided, otherwise use config
        if not sheet_name:
            sheet_name = config.get("sheet_name", "Sheet1")

        # Parse Excel file
        employees_data, actual_sheet = await parse_excel_file(
            upload_path,
            sheet_name,
            config
        )

        if not employees_data:
            # Clean up and return error - no need to keep file without data
            os.remove(upload_path)
            raise HTTPException(
                status_code=400,
                detail="No employee data found in the Excel file"
            )

        # Create import session - keep file_path for image generation
        session = ImportSession(
            filename=file.filename,
            file_path=upload_path,
            sheet_name=actual_sheet,
            total_rows=len(employees_data),
            status="active"
        )
        db.add(session)
        await db.flush()

        # Create employee records
        for emp_data in employees_data:
            employee = Employee(
                session_id=session.id,
                row_number=emp_data["row_number"],
                employee_code=emp_data.get("employee_code"),
                name=emp_data["name"],
                phone=emp_data.get("phone"),
                salary=emp_data.get("salary"),
            )
            db.add(employee)

        await db.commit()

        # Get image config for auto-generation
        image_config = None
        setting_result = await db.execute(
            select(AppSetting).where(AppSetting.key == "excel_config")
        )
        setting = setting_result.scalar_one_or_none()
        if setting and setting.value:
            image_config = {
                "image_start_col": setting.value.get("image_start_col", "B"),
                "image_end_col": setting.value.get("image_end_col", "H"),
                "image_start_row": setting.value.get("image_start_row", 4),
                "image_end_row": setting.value.get("image_end_row", 29),
            }

        # Query employee records for background generation
        emp_result_for_gen = await db.execute(
            select(Employee)
            .where(Employee.session_id == session.id)
            .order_by(Employee.row_number)
        )
        employees_for_gen = [
            {
                "id": emp.id,
                "employee_code": emp.employee_code,
                "name": emp.name
            }
            for emp in emp_result_for_gen.scalars().all()
        ]

        # Start background image generation
        await background_image_service.start_generation(
            session_id=session.id,
            excel_file_path=upload_path,
            employees=employees_for_gen,
            image_config=image_config
        )

        # Return redirect to main page (or HTMX response)
        if request.headers.get("HX-Request"):
            # HTMX request - return the employee table partial
            emp_result = await db.execute(
                select(Employee)
                .where(Employee.session_id == session.id)
                .options(selectinload(Employee.send_history))
                .order_by(Employee.row_number)
            )
            employees = emp_result.scalars().all()

            return templates.TemplateResponse(
                "partials/employee_table.html",
                {
                    "request": request,
                    "session": session,
                    "employees": employees,
                    "total_employees": len(employees),
                }
            )

        return RedirectResponse(url="/", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.get("/sheets")
async def get_sheet_names(file_path: str):
    """Get available sheet names from an Excel file."""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with ExcelParserService(file_path) as parser:
            sheets = parser.get_sheet_names()
            return {"sheets": sheets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read sheets: {str(e)}")


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an import session and all its employees."""
    result = await db.execute(
        select(ImportSession).where(ImportSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete the Excel file if it exists
    if session.file_path and os.path.exists(session.file_path):
        try:
            os.remove(session.file_path)
        except Exception:
            pass  # Ignore file deletion errors

    await db.delete(session)
    await db.commit()

    return {"status": "success", "message": "Session deleted"}


@router.get("/session/{session_id}/progress")
async def get_session_progress(session_id: str):
    """Get current image generation progress for a session."""
    progress = background_image_service.get_progress(session_id)
    if not progress:
        return {"total": 0, "completed": 0, "failed": 0, "processing": 0, "pending": 0, "is_running": False}
    return progress


@router.get("/session/{session_id}/sse")
async def session_sse(session_id: str, request: Request):
    """SSE endpoint for real-time image generation updates."""

    async def event_generator():
        queue = await background_image_service.subscribe(session_id)
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for events with timeout
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {
                        "event": data.get("type", "message"),
                        "data": json.dumps(data)
                    }

                    # Stop if generation is complete
                    if data.get("type") == "complete":
                        break

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}

        finally:
            background_image_service.unsubscribe(session_id, queue)

    return EventSourceResponse(event_generator())


@router.post("/session/{session_id}/generate-all")
async def generate_all_images(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger image generation for all employees in a session."""
    result = await db.execute(
        select(ImportSession).where(ImportSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.file_path or not os.path.exists(session.file_path):
        raise HTTPException(status_code=400, detail="Excel file not found")

    # Get employees
    emp_result = await db.execute(
        select(Employee)
        .where(Employee.session_id == session.id)
        .order_by(Employee.row_number)
    )
    employees = emp_result.scalars().all()

    if not employees:
        raise HTTPException(status_code=400, detail="No employees found")

    # Get image config
    setting_result = await db.execute(
        select(AppSetting).where(AppSetting.key == "excel_config")
    )
    setting = setting_result.scalar_one_or_none()
    image_config = None
    if setting and setting.value:
        image_config = {
            "image_start_col": setting.value.get("image_start_col", "B"),
            "image_end_col": setting.value.get("image_end_col", "H"),
            "image_start_row": setting.value.get("image_start_row", 4),
            "image_end_row": setting.value.get("image_end_row", 29),
        }

    # Prepare employee data
    employees_for_gen = [
        {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": emp.name
        }
        for emp in employees
    ]

    # Start background generation
    await background_image_service.start_generation(
        session_id=session.id,
        excel_file_path=session.file_path,
        employees=employees_for_gen,
        image_config=image_config
    )

    return {"status": "started", "total": len(employees)}
