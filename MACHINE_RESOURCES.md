# TÀI NGUYÊN MÁY TÍNH — DANH MỤC ĐẦY ĐỦ (MACHINE RESOURCES INVENTORY)
> **Người dùng**: PeaceD  
> **Thiết bị**: ASUS TUF Dash F15 FX517ZC  
> **Cập nhật**: 2026-09-17  
> **Mục đích**: Danh mục toàn bộ tài nguyên phần cứng + phần mềm trên máy. AI Agent đọc file này để biết công cụ nào có sẵn trước khi đưa ra hướng dẫn hoặc sinh lệnh.

---

## 1. PHẦN CỨNG (HARDWARE)

| Thành phần | Thông số chi tiết |
| :--- | :--- |
| **Máy tính** | ASUS TUF Dash F15 FX517ZC (Laptop) |
| **CPU** | Intel Core i5-12450H (12th Gen) — 8 Cores / 12 Threads — Base 2.0 GHz |
| **RAM** | 16 GB |
| **Ổ cứng** | 477 GB NVMe SSD (SK Hynix HFM512GD3JX013N) |
| **GPU chính (AI/CUDA)** | **NVIDIA GeForce RTX 3050 Laptop GPU** — 4 GB VRAM |
| **GPU phụ (hiển thị)** | Intel UHD Graphics — 1 GB Shared |
| **OS** | Windows 11 (x64) |

### Thông số GPU chi tiết
| Chỉ số | Giá trị |
| :--- | :--- |
| GPU Driver Version | `592.00` |
| CUDA Runtime Version (Driver) | `13.1` |
| CUDA Runtime Version (PyTorch) | **`12.4`** ← Dùng phiên bản này khi cài PyTorch |
| VRAM Total | 4096 MiB (4 GB) |
| Compute Mode | Default |
| GPU Utilization (khi rảnh) | ~0% |

> **Lưu ý khi train model**: VRAM 4GB hạn chế. Nên dùng `batch_size = 4~8` với ảnh `512×512`. Khi tràn VRAM, giảm `batch_size` hoặc dùng `torch.cuda.empty_cache()`.

---

## 2. NGÔN NGỮ LẬP TRÌNH & RUNTIME

| Công nghệ | Phiên bản | Đường dẫn / Ghi chú |
| :--- | :--- | :--- |
| **Python** (Global) | `3.12.10` | `C:\Users\PeaceD\AppData\Local\Programs\Python\Python312\` |
| **Python** (Venv dự án) | `3.12.10` | `Khoa_Luan\.venv\` — **Dùng cái này khi code KLTN** |
| **Node.js** | `v24.19.0` | `C:\Program Files\nodejs\` |
| **npm** | `11.17.0` | Đi kèm Node.js |
| **TypeScript** | `7.0.2` | Cài global qua npm |

---

## 3. CÔNG CỤ PHÁT TRIỂN (DEVELOPER TOOLS)

| Công cụ | Phiên bản | Cách gọi | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Git** | `2.55.0` | `git` | Quản lý mã nguồn |
| **GitHub CLI** | `2.100.0` | `gh` | Tạo PR, quản lý repo từ terminal |
| **Docker Desktop** | `29.7.2` | `docker` | Container hóa; *daemon tắt lúc kiểm tra* — cần khởi động Docker Desktop trước khi dùng |
| **VS Code** | Đã cài | `C:\Users\PeaceD\AppData\Local\Programs\Microsoft VS Code\` — lệnh `code` chưa vào PATH |
| **Ollama** | `0.34.1` | `ollama` | Chạy LLM local (hiện chưa có model nào được tải) |
| **orca** | Đã cài | `C:\Users\PeaceD\AppData\Local\Programs\orca\` | Công cụ xuất đồ thị Plotly sang ảnh tĩnh |

---

## 4. PACKAGE MANAGERS & GLOBAL CLI

| Công cụ | Phiên bản | Cách gọi |
| :--- | :--- | :--- |
| **pip** (global) | `25.0.1` | `pip` |
| **npm** | `11.17.0` | `npm` |
| **npx** | Đi kèm npm | `npx` |

---

## 5. THƯ VIỆN JAVASCRIPT GLOBAL (npm global)

| Package | Phiên bản | Mục đích |
| :--- | :--- | :--- |
| **`playwright`** | `1.63.0` | Tự động hóa trình duyệt (Chromium/Firefox/Webkit) — có thể gọi qua `npx playwright` |
| **`@playwright/test`** | `1.63.0` | Framework test E2E chạy trên Playwright |
| **`appium`** | `3.7.0` | Tự động hóa kiểm thử ứng dụng Mobile (iOS/Android) |
| **`typescript`** | `7.0.2` | Compiler TypeScript → JavaScript |

---

## 6. THƯ VIỆN PYTHON TRONG MÔI TRƯỜNG ẢO DỰ ÁN (`.venv`)

> **Kích hoạt**: `.\.venv\Scripts\Activate.ps1`  
> **GPU CUDA**: ✅ Hoạt động — `torch.cuda.is_available() = True`

### 6.1 Deep Learning & AI Core
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `torch` | `2.6.0+cu124` | PyTorch — nền tảng huấn luyện AI trên GPU CUDA 12.4 |
| `torchvision` | `0.21.0+cu124` | Xử lý ảnh tích hợp PyTorch |
| `torchmetrics` | `1.9.0` | Tính Dice, IoU, Recall, AUC chuẩn |
| `monai` | `1.6.0` | Medical Open Network for AI (NVIDIA) — AI Y tế chuyên sâu |
| `segmentation-models-pytorch` | `0.5.0` | U-Net, FPN, DeepLabV3+ với pretrained encoder |
| `timm` | `1.0.29` | Thư viện pretrained backbone (EfficientNet, ViT, ConvNeXt...) |

### 6.2 Xử lý Ảnh & Dữ liệu Y tế
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `pydicom` | `3.0.2` | Đọc file DICOM (.dcm) từ máy siêu âm |
| `simpleitk` | `2.5.6` | Xử lý ảnh y tế đa chiều, chuẩn hóa không gian |
| `nibabel` | `5.4.2` | Đọc định dạng NIfTI (.nii, .nii.gz) — ảnh não/3D |
| `opencv-python` | `5.0.0.93` | Thị giác máy tính, tìm đường bao, đo caliper |
| `scikit-image` | `0.26.0` | Xử lý hình thái học, phân đoạn theo ngưỡng |
| `Pillow` | `12.3.0` | Đọc/ghi ảnh PNG, JPG, BMP |
| `albumentations` | `1.4+` | Tăng cường dữ liệu medical image |
| `ImageIO` | `2.37.4` | Đọc/ghi định dạng ảnh đa dạng |

### 6.3 Tính toán & Dữ liệu
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `numpy` | `2.5.2` | Tính toán ma trận pixel, tensor |
| `pandas` | `3.0.5` | Bảng dữ liệu ca khám, thống kê |
| `scipy` | `1.18.1` | Tính toán khoa học, phân tích thống kê |
| `scikit-learn` | `1.9.1` | ROC-AUC, confusion matrix, cross-validation |

### 6.4 Đồ thị & Experiment Tracking
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `matplotlib` | `3.11.2` | Vẽ biểu đồ kết quả, đồ thị loss curve |
| `seaborn` | `0.13.2` | Biểu đồ thống kê đẹp hơn matplotlib |
| `tensorboard` | `2.21.0` | Theo dõi quá trình huấn luyện theo thời gian thực |
| `wandb` | `0.30.0` | Weights & Biases — ghi log thực nghiệm, artifact |

### 6.5 Web Backend & API
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `fastapi` | `0.141.1` | Framework API RESTful bất đồng bộ |
| `uvicorn` | `0.53.0` | ASGI server chạy FastAPI |
| `starlette` | `1.6.0` | Core HTTP của FastAPI |
| `pydantic` | `2.13.5` | Kiểm thực kiểu dữ liệu Request/Response |
| `pydantic-settings` | `2.15.0` | Đọc cấu hình từ file `.env` |
| `python-multipart` | `0.0.32` | Upload file ảnh qua HTTP |
| `httpx` | `0.28.1` | HTTP client bất đồng bộ |
| `Jinja2` | `3.1.6` | Template engine cho HTML response |

### 6.6 Cơ sở dữ liệu
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `SQLAlchemy` | `2.0.52` | ORM quản lý cơ sở dữ liệu quan hệ |
| `alembic` | `1.20.0` | Migration schema database |

### 6.7 Bảo mật & Báo cáo
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `PyJWT` | `2.14.0` | Tạo & xác thực JSON Web Token |
| `cryptography` | `50.0.1` | Mã hóa mật khẩu, hàm hash |
| `reportlab` | `5.0.1` | Xuất PDF báo cáo lâm sàng |
| `python-docx` | `1.2.0` | Xuất file Word (.docx) |

### 6.8 Môi trường Notebook & Testing
| Thư viện | Phiên bản | Vai trò |
| :--- | :--- | :--- |
| `jupyter` | `1.1.1` | Jupyter Notebook / JupyterLab |
| `jupyterlab` | `4.6.3` | Giao diện JupyterLab nâng cao |
| `ipykernel` | `7.3.0` | Python kernel cho Jupyter |
| `pytest` | `9.1.1` | Framework kiểm thử đơn vị |
| `pytest-asyncio` | `1.4.0` | Kiểm thử async endpoint FastAPI |
| `ruff` | `0.16.8` | Linter & formatter code Python (PEP8) |

---

## 7. PHẦN MỀM CÀI ĐẶT TOÀN MÁY (SYSTEM-WIDE INSTALLED)

| Phần mềm | Phiên bản | Ghi chú |
| :--- | :--- | :--- |
| **Python 3.12** | `3.12.10` | Global Python — tạo venv cho dự án |
| **Node.js** | `v24.19.0` | Runtime JS/TS |
| **Git** | `2.55.0` | Quản lý phiên bản mã nguồn |
| **GitHub CLI** | `2.100.0` | Tích hợp GitHub từ terminal |
| **Docker Desktop** | `29.7.2` | Container (cần khởi động trước khi dùng) |
| **Playwright** (npm) | `1.63.0` | Test E2E / tự động hóa trình duyệt (JS) |
| **Appium** (npm) | `3.7.0` | Test mobile (iOS/Android) |
| **TypeScript** (npm) | `7.0.2` | Compiler TypeScript global |
| **Ollama** | `0.34.1` | Chạy LLM local — hiện chưa tải model nào |
| **orca** | — | Xuất Plotly chart sang PNG/SVG |
| **NVIDIA Driver** | `592.00` | Driver GPU RTX 3050 |
| **NVIDIA GeForce Experience** | `3.25.0.84` | Quản lý driver & tối ưu game |
| **VS Code** | Đã cài | Tại `AppData\Local\Programs\Microsoft VS Code` |
| **Microsoft Office** | Đã cài | Office + Office 2013 |

---

## 8. QUY TẮC SỬ DỤNG TÀI NGUYÊN (DECISION RULES FOR AI AGENT)

1. **Luôn dùng `.venv` của dự án** — không dùng Python global khi viết code KLTN.
2. **Playwright**: Có sẵn qua `npx playwright` (JavaScript). Nếu cần dùng từ Python, cần cài thêm `pip install playwright` trong `.venv`.
3. **Docker**: Cài sẵn nhưng daemon tắt — cần người dùng mở Docker Desktop trước khi chạy lệnh `docker` bất kỳ.
4. **Ollama**: Chạy LLM local được nhưng chưa có model — gọi `ollama pull <model>` trước.
5. **GPU VRAM 4GB**: Giới hạn batch size. Dùng `batch_size ≤ 8` với ảnh 512×512. Khi train nặng nên dùng `torch.cuda.amp.autocast()` (Mixed Precision FP16) để tiết kiệm VRAM.
6. **CUDA 12.4**: Cài PyTorch luôn với flag `--index-url https://download.pytorch.org/whl/cu124`.
