/**
 * VINMEC OVARIAN ULTRASOUND AI SYSTEM - CONFIGURATION & CONSTANTS
 */

const API_BASE_URL = window.location.origin;
const API_BASE = API_BASE_URL;

// System Information & Academic Positioning
const SYSTEM_INFO = {
    name: "Hệ thống Hỗ trợ Phân đoạn Tổn thương Siêu âm Buồng trứng Human-in-the-Loop",
    nature: "Hệ thống hỗ trợ phân đoạn siêu âm buồng trứng",
    academic_context: "Khóa luận Tốt nghiệp MIS 65A - Đại học Kinh tế Quốc dân (NEU)",
    clinical_data_source: "Bệnh viện Đa khoa Quốc tế Vinmec Times City",
    core_functionality: "Hỗ trợ phân đoạn viền tổn thương và đo đạc kích thước khách quan (Segmentation & Measurement Assist)"
};
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

const VINMEC_FACILITIES = {
    times_city: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
        hospitalAddress: "Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
        addr: "Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
        tel: "Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333",
        hospitalContact: "Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333",
        code: "VM-HN-TC"
    },
    ha_long: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẠ LONG",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẠ LONG",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Số 10A, đường Lê Thánh Tông, Phường Hồng Gai, Tỉnh Quảng Ninh, Việt Nam",
        hospitalAddress: "Địa chỉ: Số 10A, đường Lê Thánh Tông, Phường Hồng Gai, Tỉnh Quảng Ninh, Việt Nam",
        addr: "Địa chỉ: Số 10A, đường Lê Thánh Tông, Phường Hồng Gai, Tỉnh Quảng Ninh, Việt Nam",
        tel: "Tel: +84 (203) 3828188 | Hotline: +84 (203) 3656115 | Cấp cứu: +84 (203) 3511599",
        hospitalContact: "Tel: +84 (203) 3828188 | Hotline: +84 (203) 3656115 | Cấp cứu: +84 (203) 3511599",
        code: "VM-HL"
    },
    central_park: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC CENTRAL PARK",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC CENTRAL PARK",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Số 208 Nguyễn Hữu Cảnh, Phường 22, Quận Bình Thạnh, TP. Hồ Chí Minh",
        hospitalAddress: "Địa chỉ: Số 208 Nguyễn Hữu Cảnh, Phường 22, Quận Bình Thạnh, TP. Hồ Chí Minh",
        addr: "Địa chỉ: Số 208 Nguyễn Hữu Cảnh, Phường 22, Quận Bình Thạnh, TP. Hồ Chí Minh",
        tel: "Tel: +84 (28) 3622 1166 | Hotline: +84 (28) 3622 1188 | Cấp cứu: +84 (28) 3622 9999",
        hospitalContact: "Tel: +84 (28) 3622 1166 | Hotline: +84 (28) 3622 1188 | Cấp cứu: +84 (28) 3622 9999",
        code: "VM-HCM-CP"
    },
    da_nang: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC ĐÀ NẴNG",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC ĐÀ NẴNG",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Đường 30 Tháng 4, Khu dân cư số 4 Nguyễn Tri Phương, Phường Hòa Cường Bắc, Quận Hải Châu, Đà Nẵng",
        hospitalAddress: "Địa chỉ: Đường 30 Tháng 4, Khu dân cư số 4 Nguyễn Tri Phương, Phường Hòa Cường Bắc, Quận Hải Châu, Đà Nẵng",
        addr: "Địa chỉ: Đường 30 Tháng 4, Khu dân cư số 4 Nguyễn Tri Phương, Phường Hòa Cường Bắc, Quận Hải Châu, Đà Nẵng",
        tel: "Tel: +84 (236) 3711 111 | Hotline: +84 (236) 3711 113 | Cấp cứu: +84 (236) 3611 611",
        hospitalContact: "Tel: +84 (236) 3711 111 | Hotline: +84 (236) 3711 113 | Cấp cứu: +84 (236) 3611 611",
        code: "VM-DN"
    },
    hai_phong: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẢI PHÒNG",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẢI PHÒNG",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Đường Võ Nguyên Giáp, Phường Vĩnh Niệm, Quận Lê Chân, Hải Phòng",
        hospitalAddress: "Địa chỉ: Đường Võ Nguyên Giáp, Phường Vĩnh Niệm, Quận Lê Chân, Hải Phòng",
        addr: "Địa chỉ: Đường Võ Nguyên Giáp, Phường Vĩnh Niệm, Quận Lê Chân, Hải Phòng",
        tel: "Tel: +84 (225) 7309 888 | Hotline: +84 (225) 7309 890 | Cấp cứu: +84 (225) 7309 115",
        hospitalContact: "Tel: +84 (225) 7309 888 | Hotline: +84 (225) 7309 890 | Cấp cứu: +84 (225) 7309 115",
        code: "VM-HP"
    },
    nha_trang: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC NHA TRANG",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC NHA TRANG",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Số 42A Trần Phú, Phường Vĩnh Nguyên, TP. Nha Trang, Tỉnh Khánh Hòa",
        hospitalAddress: "Địa chỉ: Số 42A Trần Phú, Phường Vĩnh Nguyên, TP. Nha Trang, Tỉnh Khánh Hòa",
        addr: "Địa chỉ: Số 42A Trần Phú, Phường Vĩnh Nguyên, TP. Nha Trang, Tỉnh Khánh Hòa",
        tel: "Tel: +84 (258) 3900 168 | Hotline: +84 (258) 3900 170 | Cấp cứu: +84 (258) 3900 115",
        hospitalContact: "Tel: +84 (258) 3900 168 | Hotline: +84 (258) 3900 170 | Cấp cứu: +84 (258) 3900 115",
        code: "VM-NT"
    },
    phu_quoc: {
        name: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC PHÚ QUỐC",
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC PHÚ QUỐC",
        dept: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        address: "Bãi Dài, Xã Gành Dầu, Thành phố Phú Quốc, Tỉnh Kiên Giang",
        hospitalAddress: "Địa chỉ: Bãi Dài, Xã Gành Dầu, Thành phố Phú Quốc, Tỉnh Kiên Giang",
        addr: "Địa chỉ: Bãi Dài, Xã Gành Dầu, Thành phố Phú Quốc, Tỉnh Kiên Giang",
        tel: "Tel: +84 (297) 398 5588 | Hotline: +84 (297) 398 5590 | Cấp cứu: +84 (297) 398 5115",
        hospitalContact: "Tel: +84 (297) 398 5588 | Hotline: +84 (297) 398 5590 | Cấp cứu: +84 (297) 398 5115",
        code: "VM-PQ"
    }
};
