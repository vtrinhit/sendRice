"""
Main Router
Handles the main page and Excel file upload.
"""
import os
import uuid
import shutil
from typing import Optional
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.config import settings
from app.models import ImportSession, Employee, AppSetting
from app.services.excel_parser import parse_excel_file, ExcelParserService


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
            # Clean up and return error
            os.remove(upload_path)
            raise HTTPException(
                status_code=400,
                detail="No employee data found in the Excel file"
            )

        # Create import session
        session = ImportSession(
            filename=file.filename,
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

        # Return redirect to main page (or HTMX response)
        if request.headers.get("HX-Request"):
            # HTMX request - return the employee table partial
            emp_result = await db.execute(
                select(Employee)
                .where(Employee.session_id == session.id)
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

    await db.delete(session)
    await db.commit()

    return {"status": "success", "message": "Session deleted"}
