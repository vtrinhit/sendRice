# SendRice

**Tool gửi bảng lương nhân viên qua Zalo**

SendRice là ứng dụng web giúp HR/Kế toán gửi thông báo lương đến nhân viên qua Zalo một cách tự động và hiệu quả.

## Tính Năng

- **Authentication** - Đăng nhập bảo mật với JWT, dark mode UI
- **Import Excel** - Upload file Excel, tự động parse danh sách nhân viên
- **Tạo ảnh bảng lương** - Chuyển đổi sheet phiếu lương thành ảnh PNG
- **Gửi Zalo qua n8n** - Tích hợp webhook n8n để gửi tin nhắn Zalo kèm ảnh base64
- **Batch processing** - Chọn nhiều nhân viên và xử lý hàng loạt
- **Cấu hình linh hoạt** - Tùy chỉnh mapping cột Excel, webhook URL
- **Dark Mode** - Hỗ trợ giao diện tối, lưu preference

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11 + FastAPI |
| Frontend | Jinja2 + HTMX + Alpine.js + Tailwind CSS |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Excel | openpyxl |
| Image Gen | LibreOffice + PyMuPDF |
| Container | Docker Compose |

## Yêu Cầu

- Docker & Docker Compose
- LibreOffice (local dev only - included in Docker)
- n8n instance với Zalo webhook

---

## Cài Đặt Nhanh (Docker)

### 1. Clone repository

```bash
git clone <repository-url>
cd sendRice
```

### 2. Cấu hình environment

```bash
cp .env.example .env
```

Chỉnh sửa file `.env`:

```env
# Database
DB_PASSWORD=your_secure_password_here

# Application
SECRET_KEY=your_secret_key_min_32_characters

# JWT Authentication
JWT_SECRET_KEY=your_jwt_secret_key_change_this
JWT_EXPIRE_HOURS=24

# n8n Webhook
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/send-zalo
```

### 3. Chạy ứng dụng

```bash
# Start containers
docker-compose up -d app db

# Khởi tạo database
docker-compose exec app python scripts/init_db.py
```

### 4. Tạo admin user

```bash
docker-compose build app  # Rebuild nếu lần đầu
docker-compose up -d app
docker-compose exec app python scripts/create_admin.py -u admin -p your_password
```

### 5. Truy cập

- URL: http://localhost:8000
- Đăng nhập với admin / your_password

---

## Cài Đặt Local (Không Docker)

### 1. Yêu cầu

- Python 3.11+
- PostgreSQL 16+
- LibreOffice (để generate ảnh lương)

### 2. Setup

```bash
# Tạo virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Cấu hình environment

Tạo file `.env`:

```env
DATABASE_URL=postgresql+asyncpg://sendrice:password@localhost:5432/sendrice
JWT_SECRET_KEY=your-jwt-secret-key-change-this
JWT_EXPIRE_HOURS=24
N8N_WEBHOOK_URL=https://your-n8n-webhook-url
SECRET_KEY=your-secret-key
```

### 4. Chạy PostgreSQL (Docker)

```bash
docker run -d --name sendrice-db \
    -e POSTGRES_USER=sendrice \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_DB=sendrice \
    -p 5432:5432 \
    postgres:16-alpine
```

Hoặc sử dụng docker-compose chỉ cho database:

```bash
docker-compose up -d db
```

### 5. Khởi tạo database và admin

```bash
# Init database tables
python scripts/init_db.py

# Tạo admin user
python scripts/create_admin.py -u admin -p your_password
```

### 6. Chạy ứng dụng

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Truy cập

- URL: http://localhost:8000
- Đăng nhập với admin / your_password

---

## Authentication

### Tổng quan

- **JWT Token** lưu trong HTTP-only cookie
- **Token expiry**: 24 giờ (configurable)
- **Password hashing**: bcrypt

### Quản lý Admin

```bash
# Tạo admin mới
python scripts/create_admin.py -u admin -p password123

# Với tên đầy đủ
python scripts/create_admin.py -u admin -p password123 -n "Admin Name"
```

### Thay đổi mật khẩu

Chạy lại script với cùng username sẽ cập nhật password:

```bash
python scripts/create_admin.py -u admin -p new_password
```

---

## Sử Dụng

### 1. Đăng nhập

1. Truy cập http://localhost:8000
2. Sẽ redirect đến `/login`
3. Nhập username/password
4. Nhấn "Đăng nhập"

### 2. Import Excel

1. Vào trang chính
2. Upload file Excel (.xlsx)
3. Chọn tên sheet (mặc định: Sheet1)
4. Nhấn "Upload & Import"

### 3. Cấu hình mapping cột

Vào **Cài đặt** > **Cấu hình Excel**:

| Field | Mô tả | Mặc định |
|-------|-------|----------|
| Sheet name | Tên sheet chứa dữ liệu | Sheet1 |
| Header row | Hàng tiêu đề | 1 |
| Data start row | Hàng bắt đầu dữ liệu | 2 |
| Code column | Cột mã nhân viên | A |
| Name column | Cột họ tên | B |
| Phone column | Cột số điện thoại | C |
| Salary column | Cột lương | D |

### 4. Cấu hình ảnh lương

| Field | Mô tả | Mặc định |
|-------|-------|----------|
| Image start col | Cột bắt đầu vùng ảnh | B |
| Image end col | Cột kết thúc vùng ảnh | H |
| Image start row | Hàng bắt đầu vùng ảnh | 4 |
| Image end row | Hàng kết thúc vùng ảnh | 29 |

### 5. Tạo ảnh và gửi

1. Chọn nhân viên (checkbox)
2. Nhấn **"Tạo ảnh"** để generate ảnh lương
3. Nhấn **"Gửi Zalo"** để gửi thông báo

### 6. Dark Mode

- Click icon mặt trời/trăng trên navbar để toggle
- Preference được lưu trong localStorage

---

## n8n Webhook Format

### Request (SendRice → n8n)

```json
{
    "sdt": "0901234567",
    "ten": "Nguyen Van A",
    "luong": 15000000,
    "hinhanh": "data:image/png;base64,iVBORw0KGgoAAAANS..."
}
```

### Response (n8n → SendRice)

```json
{
    "status": "success",
    "message": null
}
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/login` | Trang đăng nhập |
| POST | `/login` | Xử lý đăng nhập |
| POST | `/logout` | Đăng xuất |

### Main

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Trang chính (requires auth) |
| POST | `/upload` | Upload Excel |
| DELETE | `/session/{id}` | Xóa session |
| GET | `/session/{id}/progress` | Progress tạo ảnh |
| GET | `/session/{id}/sse` | SSE real-time updates |

### Employees

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/employees` | Danh sách nhân viên |
| GET | `/api/employees/{id}` | Chi tiết nhân viên |
| PATCH | `/api/employees/{id}` | Cập nhật nhân viên |
| POST | `/api/employees/{id}/generate-image` | Tạo ảnh lương |
| POST | `/api/employees/{id}/send` | Gửi thông báo |
| GET | `/api/employees/{id}/preview` | Preview ảnh |
| POST | `/api/employees/batch/generate-images` | Tạo ảnh hàng loạt |
| POST | `/api/employees/batch/send` | Gửi hàng loạt |

### Settings

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/settings/page` | Trang cài đặt |
| GET | `/api/settings` | Lấy tất cả settings |
| POST | `/api/settings/excel` | Lưu cấu hình Excel |
| POST | `/api/settings/webhook` | Lưu cấu hình webhook |
| POST | `/api/settings/webhook/test` | Test webhook |

### Health

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/health` | Health check |

---

## Cấu Trúc Project

```
sendRice/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic settings
│   ├── database.py          # SQLAlchemy async
│   ├── helpers.py           # Utility functions
│   ├── models/              # ORM models
│   │   ├── __init__.py
│   │   ├── employee.py
│   │   ├── import_session.py
│   │   ├── send_history.py
│   │   ├── settings.py
│   │   └── user.py          # User model (auth)
│   ├── schemas/             # Pydantic schemas
│   │   ├── auth.py          # Auth schemas
│   │   ├── employee.py
│   │   ├── send.py
│   │   └── settings.py
│   ├── services/            # Business logic
│   │   ├── auth_service.py  # JWT & password utils
│   │   ├── excel_parser.py
│   │   ├── salary_slip_service_optimized.py
│   │   ├── background_image_service.py
│   │   └── webhook_service.py
│   ├── dependencies/        # FastAPI dependencies
│   │   └── auth.py          # Auth dependencies
│   ├── routers/             # API routes
│   │   ├── auth.py          # Login/logout routes
│   │   ├── main.py
│   │   ├── employees.py
│   │   └── settings.py
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html        # Base layout + navbar
│   │   ├── login.html       # Login page
│   │   ├── index.html       # Main dashboard
│   │   ├── settings.html    # Settings page
│   │   └── partials/        # HTMX partials
│   └── static/              # Static files
│       ├── css/
│       │   └── custom.css   # Custom styles
│       └── js/
│           └── app.js       # JS utilities
├── scripts/
│   ├── init_db.py           # Database init
│   └── create_admin.py      # Admin user creation
├── nginx/
│   └── nginx.conf           # Nginx config
├── docs/
│   └── DESIGN.md            # UI/UX documentation
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── CLAUDE.md                # AI assistant instructions
└── .env.example
```

---

## Environment Variables

| Variable | Mô tả | Required |
|----------|-------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `DB_PASSWORD` | Database password (Docker) | Yes |
| `SECRET_KEY` | App secret key | Yes |
| `JWT_SECRET_KEY` | JWT signing key | Yes |
| `JWT_EXPIRE_HOURS` | Token expiry (hours) | No (default: 24) |
| `N8N_WEBHOOK_URL` | n8n webhook endpoint | No |

---

## Troubleshooting

### Lỗi bcrypt/passlib

```bash
# Pin bcrypt version trong requirements.txt
bcrypt==4.0.1
```

### Lỗi "LibreOffice not found"

```bash
# Windows: Cài LibreOffice từ https://www.libreoffice.org/download
# Đảm bảo soffice.exe trong PATH

# Linux:
sudo apt install libreoffice-calc

# Trong Docker đã cài sẵn
```

### Lỗi kết nối database

```bash
# Kiểm tra container database
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d db
docker-compose exec app python scripts/init_db.py
```

### Không thể đăng nhập

```bash
# Tạo lại admin user
docker-compose exec app python scripts/create_admin.py -u admin -p new_password

# Hoặc local:
python scripts/create_admin.py -u admin -p new_password
```

### Script không tìm thấy trong container

```bash
# Rebuild container để copy files mới
docker-compose build app
docker-compose up -d app
```

---

## Production Deployment

### Cấu hình SSL (Let's Encrypt)

```bash
# 1. Cập nhật domain trong nginx/nginx.conf
sed -i 's/your-domain.com/example.com/g' nginx/nginx.conf

# 2. Chạy nginx để lấy certificate
docker-compose up -d nginx

# 3. Lấy certificate
sudo certbot certonly --webroot -w ./certbot/www -d example.com

# 4. Copy certificates
sudo cp /etc/letsencrypt/live/example.com/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/example.com/privkey.pem ./nginx/ssl/

# 5. Restart nginx
docker-compose restart nginx
```

### Security Checklist

- [ ] Đổi `JWT_SECRET_KEY` sang key mạnh (32+ characters)
- [ ] Đổi `SECRET_KEY` sang key mạnh
- [ ] Đổi `DB_PASSWORD` sang password mạnh
- [ ] Cấu hình SSL/HTTPS
- [ ] Đổi password admin mặc định
- [ ] Cấu hình firewall (chỉ mở ports cần thiết)

---

## Development

### Chạy tests

```bash
pytest tests/ -v
```

### Code style

```bash
# Format code
black app/

# Lint
flake8 app/
```

---

## Contributing

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Tạo Pull Request

---

## License

MIT License - xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## Support

- Issues: [GitHub Issues](https://github.com/your-repo/sendrice/issues)
