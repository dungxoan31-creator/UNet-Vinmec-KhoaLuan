/**
 * VINMEC OVARIAN ULTRASOUND AI SYSTEM - UNIFIED API CLIENT
 */

const ApiClient = {
    // Health & System
    async getHealth() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/health`);
        return await res.json();
    },

    async getDashboardStats() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/stats`);
        return await res.json();
    },

    // Auth & Users
    async getUsers() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/auth/users`);
        return await res.json();
    },

    async getCurrentUser() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/auth/current-user`);
        return await res.json();
    },

    // Clinical Cases
    async getSamples() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/samples`);
        return await res.json();
    },

    async getCases(params = {}) {
        const query = new URLSearchParams();
        if (params.search) query.append("search", params.search);
        if (params.status && params.status !== "ALL") query.append("status", params.status);
        if (params.date) query.append("date", params.date);
        
        const url = `${API_BASE_URL}/api/cases${query.toString() ? '?' + query.toString() : ''}`;
        const res = await authenticatedFetch(url);
        return await res.json();
    },

    async getCaseDetail(studyId) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/cases/${studyId}`);
        return await res.json();
    },

    async createCase(caseData) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/cases`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(caseData)
        });
        return await res.json();
    },

    async deleteCase(studyId) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/cases/${studyId}`, {
            method: "DELETE"
        });
        return await res.json();
    },

    // Upload, IQA & Inference
    async uploadImage(formData) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/upload`, {
            method: "POST",
            body: formData
        });
        return await res.json();
    },

    async validateImage(imageId) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/validate-image?image_id=${encodeURIComponent(imageId)}`, {
            method: "POST"
        });
        return await res.json();
    },

    async runPrediction(imageId) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/predict/${encodeURIComponent(imageId)}`, {
            method: "POST"
        });
        return await res.json();
    },

    async calibrateSpacing(imageId, spacingMm) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/images/${encodeURIComponent(imageId)}/calibrate?pixel_spacing_mm=${encodeURIComponent(spacingMm)}`, {
            method: "POST"
        });
        if (!res.ok) throw new Error("Không thể hiệu chuẩn tỉ lệ pixel.");
        return await res.json();
    },

    async evaluateCdss(cdssPayload) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/v1/cdss/evaluate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cdssPayload)
        });
        if (!res.ok) throw new Error("Không thể đánh giá CDSS.");
        return await res.json();
    },

    // Review & Reports
    async submitReview(reviewData) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/review`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reviewData)
        });
        return await res.json();
    },

    async generateReportPdf(reportPayload) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/generate-report`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reportPayload)
        });
        if (!res.ok) throw new Error("Không thể tạo file báo cáo PDF.");
        return await res.blob();
    },

    // Admin Portal
    async getAdminModels() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/admin/models`);
        return await res.json();
    },

    async getAuditLogs(limit = 50) {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/admin/audit-logs?limit=${limit}`);
        return await res.json();
    },

    async getDoctorStats() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/admin/doctor-stats`);
        return await res.json();
    },

    async exportDataset() {
        const res = await authenticatedFetch(`${API_BASE_URL}/api/admin/export-dataset`);
        if (!res.ok) throw new Error('Không có quyền xuất dữ liệu.');
        const url = URL.createObjectURL(await res.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = 'review_summary.json';
        link.click();
        URL.revokeObjectURL(url);
    }
};
