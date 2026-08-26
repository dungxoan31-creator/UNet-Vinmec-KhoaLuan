/**
 * VINMEC OVARIAN ULTRASOUND AI SYSTEM - CONFIGURATION & CONSTANTS
 */

const API_BASE_URL = window.location.origin;
const API_BASE = API_BASE_URL;

// Vinmec 7-Hospital Facility Metadata
const FACILITIES_METADATA = {
    "times_city": {
        "name": "BỆNH VIỆN ĐKQT VINMEC TIMES CITY",
        "address": "458 Minh Khai, Q. Hai Bà Trưng, Hà Nội",
        "hotline": "024 3974 3556",
        "emergency": "024 3974 4333",
        "code": "VM-HN-TC"
    },
    "central_park": {
        "name": "BỆNH VIỆN ĐKQT VINMEC CENTRAL PARK",
        "address": "208 Nguyễn Hữu Cảnh, P. 22, Q. Bình Thạnh, TP. HCM",
        "hotline": "028 3622 1166",
        "emergency": "028 3622 1188",
        "code": "VM-HCM-CP"
    },
    "da_nang": {
        "name": "BỆNH VIỆN ĐKQT VINMEC ĐÀ NẴNG",
        "address": "Đường 30 Tháng 4, P. Hòa Cường Bắc, Q. Hải Châu, Đà Nẵng",
        "hotline": "0236 3711 111",
        "emergency": "0236 3711 115",
        "code": "VM-DN"
    },
    "nha_trang": {
        "name": "BỆNH VIỆN ĐKQT VINMEC NHA TRANG",
        "address": "42A Trần Phú, P. Vĩnh Nguyên, TP. Nha Trang, Khánh Hòa",
        "hotline": "0258 3900 168",
        "emergency": "0258 3900 199",
        "code": "VM-NT"
    },
    "hai_phong": {
        "name": "BỆNH VIỆN ĐKQT VINMEC HẢI PHÒNG",
        "address": "Võ Nguyên Giáp, P. Vĩnh Niệm, Q. Lê Chân, Hải Phòng",
        "hotline": "0225 7309 888",
        "emergency": "0225 7309 115",
        "code": "VM-HP"
    },
    "ha_long": {
        "name": "BỆNH VIỆN ĐKQT VINMEC HẠ LONG",
        "address": "10A Lê Thánh Tông, TP. Hạ Long, Quảng Ninh",
        "hotline": "0203 3828 188",
        "emergency": "0203 3828 115",
        "code": "VM-HL"
    },
    "phu_quoc": {
        "name": "BỆNH VIỆN ĐKQT VINMEC PHÚ QUỐC",
        "address": "Bãi Dài, Xã Gành Dầu, TP. Phú Quốc, Kiên Giang",
        "hotline": "0297 3985 588",
        "emergency": "0297 3985 522",
        "code": "VM-PQ"
    }
};

// Standard Clinical Ultrasound Macro Templates
const MACROS = {
    "normal": "Hình ảnh buồng trứng kích thước và hồi âm bình thường. Không phát hiện khối u hoặc nang bất thường. Dịch cùng đồ Douglas tự do (-).",
    "simple_cyst": "Phát hiện tổn thương dạng nang dịch trong đồng nhất buồng trứng. Vách mỏng < 3mm, bờ đều rõ nét, không chồi nhú, không vách hóa, tăng âm thành sau điển hình. Đánh giá O-RADS 2 (Lành tính cao).",
    "dermoid": "Khối u buồng trứng kích thước trung bình, hồi âm hỗn hợp kèm nốt Rokitansky tăng âm sáng và bóng cản âm lưng điển hình của u bì (Teratoma). Không tăng sinh mạch trên Doppler màu. Đánh giá O-RADS 2.",
    "endometrioma": "Tổn thương dạng nang buồng trứng chứa hồi âm hạt mịn đồng nhất dạng kính mờ (Ground-glass echogenicity), thành nang dày đều, không chồi nhú mạch máu. Hình ảnh điển hình của u lạc nội mạc tử cung (Chocolate cyst). Đánh giá O-RADS 3.",
    "mucinous": "Khối u nang đa thùy buồng trứng, chứa nhiều vách ngăn mỏng < 3mm, hồi âm dịch nhầy lợn cợn nhẹ, không có thành phần đặc hoặc nốt nhú tăng sinh mạch. Đánh giá O-RADS 3."
};

// O-RADS Classification Risk Mapping
const ORADS_MAP = {
    "NORMAL": { category: "O-RADS 1", label: "Sinh lý bình thường (< 1% ác tính)", badgeClass: "badge-success", color: "#10b981" },
    "CYSTIC": { category: "O-RADS 2", label: "Gần như chắc chắn lành tính (< 1% ác tính)", badgeClass: "badge-success", color: "#10b981" },
    "DERMOID": { category: "O-RADS 2", label: "U bì điển hình lành tính (< 1% ác tính)", badgeClass: "badge-success", color: "#10b981" },
    "ENDOMETRIOMA": { category: "O-RADS 3", label: "Nguy cơ ác tính thấp (1% - 10%)", badgeClass: "badge-warning", color: "#f59e0b" },
    "MUCINOUS": { category: "O-RADS 3", label: "Nguy cơ ác tính thấp (1% - 10%)", badgeClass: "badge-warning", color: "#f59e0b" },
    "SOLID": { category: "O-RADS 4", label: "Nguy cơ ác tính trung bình (10% - 50%)", badgeClass: "badge-danger", color: "#ef4444" }
};
