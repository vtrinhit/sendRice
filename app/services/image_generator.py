"""
Image Generator Service
Generates salary slip images from Excel data using HTML templates.
"""
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from html2image import Html2Image
from pathlib import Path

from app.config import settings


class ImageGeneratorService:
    """Service for generating salary slip images."""

    def __init__(self):
        """Initialize the image generator."""
        self.output_dir = settings.temp_images_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize html2image with Chromium
        self.hti = Html2Image(
            output_path=self.output_dir,
            custom_flags=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--hide-scrollbars',
            ]
        )

    def generate_salary_image(
        self,
        employee_name: str,
        employee_data: Dict[str, Any],
        rows_data: Optional[List[List[Dict]]] = None,
        custom_html: Optional[str] = None,
    ) -> str:
        """
        Generate a salary slip image for an employee.

        Args:
            employee_name: Name of the employee
            employee_data: Employee data dictionary
            rows_data: Optional Excel row data for detailed slip
            custom_html: Optional custom HTML template

        Returns:
            Path to generated image file
        """
        # Generate unique filename
        filename = f"salary_{uuid.uuid4().hex[:12]}.png"

        # Generate HTML content
        if custom_html:
            html_content = custom_html
        elif rows_data:
            html_content = self._generate_html_from_rows(employee_name, employee_data, rows_data)
        else:
            html_content = self._generate_simple_html(employee_name, employee_data)

        # Generate image
        self.hti.screenshot(
            html_str=html_content,
            save_as=filename,
            size=(800, 600)
        )

        return os.path.join(self.output_dir, filename)

    def _generate_simple_html(self, employee_name: str, employee_data: Dict[str, Any]) -> str:
        """Generate simple salary slip HTML."""
        salary = employee_data.get("salary", 0)
        formatted_salary = f"{salary:,.0f}".replace(",", ".") + " VND" if salary else "N/A"
        employee_code = employee_data.get("employee_code", "")
        current_month = datetime.now().strftime("%m/%Y")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600&family=Fira+Code&display=swap');

                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: 'Fira Sans', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px;
                    min-height: 100vh;
                }}

                .salary-slip {{
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    overflow: hidden;
                    max-width: 600px;
                    margin: 0 auto;
                }}

                .header {{
                    background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}

                .header h1 {{
                    font-size: 24px;
                    font-weight: 600;
                    margin-bottom: 8px;
                }}

                .header .period {{
                    font-size: 14px;
                    opacity: 0.9;
                }}

                .content {{
                    padding: 30px;
                }}

                .employee-info {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px dashed #E5E7EB;
                }}

                .info-item {{
                    text-align: center;
                }}

                .info-label {{
                    font-size: 12px;
                    color: #6B7280;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 4px;
                }}

                .info-value {{
                    font-size: 16px;
                    font-weight: 600;
                    color: #1F2937;
                }}

                .salary-section {{
                    background: linear-gradient(135deg, #F97316 0%, #EA580C 100%);
                    border-radius: 12px;
                    padding: 30px;
                    text-align: center;
                    color: white;
                }}

                .salary-label {{
                    font-size: 14px;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                    opacity: 0.9;
                    margin-bottom: 8px;
                }}

                .salary-amount {{
                    font-family: 'Fira Code', monospace;
                    font-size: 36px;
                    font-weight: 600;
                }}

                .footer {{
                    text-align: center;
                    padding: 20px;
                    color: #9CA3AF;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="salary-slip">
                <div class="header">
                    <h1>BẢNG LƯƠNG NHÂN VIÊN</h1>
                    <div class="period">Kỳ lương: {current_month}</div>
                </div>

                <div class="content">
                    <div class="employee-info">
                        <div class="info-item">
                            <div class="info-label">Mã NV</div>
                            <div class="info-value">{employee_code or 'N/A'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Họ và Tên</div>
                            <div class="info-value">{employee_name}</div>
                        </div>
                    </div>

                    <div class="salary-section">
                        <div class="salary-label">Thực Lãnh</div>
                        <div class="salary-amount">{formatted_salary}</div>
                    </div>
                </div>

                <div class="footer">
                    Đây là phiếu lương tự động. Vui lòng liên hệ HR nếu có thắc mắc.
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_html_from_rows(
        self,
        employee_name: str,
        employee_data: Dict[str, Any],
        rows_data: List[List[Dict]]
    ) -> str:
        """Generate HTML table from Excel rows data."""
        current_month = datetime.now().strftime("%m/%Y")
        employee_row = employee_data.get("row_number", 0)

        # Build table rows
        table_rows = ""
        for row in rows_data:
            cells = ""
            is_employee_row = any(cell.get("is_employee_row") for cell in row)
            row_class = "highlight-row" if is_employee_row else ""

            for cell in row:
                value = cell.get("value", "")
                cells += f"<td>{value}</td>"

            table_rows += f"<tr class='{row_class}'>{cells}</tr>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600&family=Fira+Code&display=swap');

                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: 'Fira Sans', sans-serif;
                    background: #F3F4F6;
                    padding: 30px;
                }}

                .container {{
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                    max-width: 900px;
                    margin: 0 auto;
                }}

                .header {{
                    background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%);
                    color: white;
                    padding: 20px 30px;
                }}

                .header h1 {{
                    font-size: 20px;
                    font-weight: 600;
                }}

                .header .subtitle {{
                    font-size: 14px;
                    opacity: 0.9;
                    margin-top: 4px;
                }}

                .table-container {{
                    padding: 20px;
                    overflow-x: auto;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-family: 'Fira Code', monospace;
                    font-size: 13px;
                }}

                th, td {{
                    border: 1px solid #E5E7EB;
                    padding: 10px 12px;
                    text-align: left;
                }}

                th {{
                    background: #F9FAFB;
                    font-weight: 600;
                    color: #374151;
                }}

                .highlight-row {{
                    background: linear-gradient(90deg, #FEF3C7 0%, #FDE68A 100%);
                    font-weight: 600;
                }}

                .highlight-row td {{
                    border-color: #F59E0B;
                }}

                .footer {{
                    text-align: center;
                    padding: 15px;
                    color: #9CA3AF;
                    font-size: 11px;
                    border-top: 1px solid #E5E7EB;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>BẢNG LƯƠNG - {employee_name}</h1>
                    <div class="subtitle">Kỳ lương: {current_month}</div>
                </div>

                <div class="table-container">
                    <table>
                        {table_rows}
                    </table>
                </div>

                <div class="footer">
                    Phiếu lương tự động - Liên hệ HR nếu có thắc mắc
                </div>
            </div>
        </body>
        </html>
        """

    def cleanup_image(self, image_path: str) -> bool:
        """Delete a temporary image file."""
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                return True
            return False
        except Exception:
            return False

    def cleanup_old_images(self, max_age_hours: int = 24) -> int:
        """Clean up images older than specified hours."""
        cleaned = 0
        now = datetime.now()

        for filename in os.listdir(self.output_dir):
            if filename.startswith("salary_") and filename.endswith(".png"):
                file_path = os.path.join(self.output_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                age_hours = (now - file_time).total_seconds() / 3600

                if age_hours > max_age_hours:
                    try:
                        os.remove(file_path)
                        cleaned += 1
                    except Exception:
                        pass

        return cleaned


# Singleton instance
image_generator = ImageGeneratorService()
