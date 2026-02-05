# SendRice

**Tool gửi bảng lương nhân viên qua Zalo**

SendRice là ứng dụng web giúp HR/Kế toán gửi thông báo lương đến nhân viên qua Zalo một cách tự động và hiệu quả.

## Tính Năng

- **Import Excel** - Upload file Excel, tự động parse danh sách nhân viên
- **Tạo ảnh bảng lương** - Chuyển đổi dữ liệu Excel thành ảnh PNG đẹp mắt
- **Upload Google Drive** - Tự động upload ảnh lên Drive với cấu trúc thư mục theo năm/tháng
- **Gửi Zalo qua n8n** - Tích hợp webhook n8n để gửi tin nhắn Zalo
- **Batch processing** - Chọn nhiều nhân viên và gửi hàng loạt
- **Cấu hình linh hoạt** - Tùy chỉnh mapping cột Excel, webhook URL, Drive folder

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11 + FastAPI |
| Frontend | Jinja2 + HTMX + Alpine.js |
| Database | PostgreSQL 15 |
| Excel | openpyxl |
| Image Gen | html2image (Chromium) |
| Container | Docker Compose |

## Yêu Cầu

- Docker & Docker Compose
- Google Cloud credentials (cho Google Drive API)
- n8n instance với Zalo webhook

## Cài Đặt

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

# Google Drive (optional)
GOOGLE_DRIVE_FOLDER_ID=your_folder_id

# n8n Webhook
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/send-zalo
```

### 3. Cấu hình Google Drive (Optional)

1. Tạo project trên [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Drive API
3. Tạo Service Account và download JSON key
4. Đặt file vào `credentials/google_credentials.json`
5. Share folder Drive với email của Service Account

### 4. Chạy ứng dụng

```bash
# Development (không có nginx)
docker-compose up -d app db

# Production (với nginx + SSL)
docker-compose up -d
```

### 5. Khởi tạo database

```bash
docker-compose exec app python scripts/init_db.py
```

### 6. Truy cập

- Development: http://localhost:8000
- Production: https://your-domain.com

## Cấu Hình SSL (Production)

### Sử dụng Let's Encrypt

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

## Sử Dụng

### 1. Import Excel

1. Vào trang chính
2. Upload file Excel (.xlsx)
3. Chọn tên sheet (mặc định: Sheet1)
4. Nhấn "Upload & Import"

### 2. Cấu hình mapping cột

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

### 3. Tạo ảnh và gửi

1. Chọn nhân viên (checkbox)
2. Nhấn **"Tạo ảnh"** để generate ảnh lương
3. Nhấn **"Gửi Zalo"** để gửi thông báo

## n8n Webhook Format

### Request (SendRice → n8n)

```json
{
    "SDT": "0901234567",
    "Ten": "Nguyen Van A",
    "Luong": 15000000,
    "HinhAnhURL": "https://drive.google.com/uc?id=xxx"
}
```

### Response (n8n → SendRice)

```json
{
    "status": "success",
    "message": null
}
```

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Trang chính |
| POST | `/upload` | Upload Excel |
| GET | `/api/employees` | Danh sách nhân viên |
| POST | `/api/employees/{id}/generate-image` | Tạo ảnh lương |
| POST | `/api/employees/{id}/send` | Gửi thông báo |
| POST | `/api/employees/batch/send` | Gửi hàng loạt |
| GET | `/api/settings/page` | Trang cài đặt |
| POST | `/api/settings/excel` | Lưu cấu hình Excel |
| POST | `/api/settings/webhook` | Lưu cấu hình webhook |
| GET | `/health` | Health check |

## Cấu Trúc Project

```
sendRice/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic settings
│   ├── database.py          # SQLAlchemy async
│   ├── models/              # ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   ├── routers/             # API routes
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JS
├── scripts/
│   └── init_db.py          # Database init
├── nginx/
│   └── nginx.conf          # Nginx config
├── docs/
│   └── DESIGN.md           # UI/UX documentation
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Development

### Chạy local (không Docker)

```bash
# 1. Tạo virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Chạy PostgreSQL (Docker)
docker run -d --name sendrice-db \
    -e POSTGRES_USER=sendrice \
    -e POSTGRES_PASSWORD=sendrice \
    -e POSTGRES_DB=sendrice \
    -p 5432:5432 \
    postgres:15-alpine

# 4. Chạy app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Chạy tests

```bash
pytest tests/ -v
```

## Troubleshooting

### Lỗi "Chromium not found"

```bash
# Trong Docker, đã cài sẵn. Nếu chạy local:
apt-get install chromium chromium-driver
```

### Lỗi kết nối database

```bash
# Kiểm tra container database
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d
docker-compose exec app python scripts/init_db.py --reset
```

### Lỗi Google Drive

1. Kiểm tra file credentials tồn tại
2. Kiểm tra Service Account có quyền truy cập folder
3. Kiểm tra Drive API đã được enable

## Contributing

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Tạo Pull Request

## License

MIT License - xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## Support

- Issues: [GitHub Issues](https://github.com/your-repo/sendrice/issues)
- Email: support@example.com
