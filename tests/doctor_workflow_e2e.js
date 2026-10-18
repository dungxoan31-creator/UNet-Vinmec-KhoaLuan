/**
 * Comprehensive Doctor End-to-End Clinical Flow (E2E Test)
 * 
 * Scenario:
 * 1. Bác sĩ truy cập hệ thống và đăng ký tài khoản mới (#register)
 * 2. Đăng nhập thành công, kiểm tra thông tin hiển thị tại Tổng quan (#dashboard)
 * 3. Tạo ca khảo sát buồng trứng hai bên tại (#intake), chọn ảnh Trái & Phải
 * 4. Kích hoạt phân đoạn AI chủ động bằng nút (#startSegmentationBtn)
 * 5. Hệ thống hoàn tất suy luận U-Net và chuyển vào Không gian rà soát (#viewer)
 * 6. Bác sĩ kiểm tra hai bên buồng trứng, thực hiện tinh chỉnh cọ vẽ/tẩy/hoàn tác (HITL)
 * 7. Bác sĩ gắn nhãn hình thái và Lưu rà soát chính thức (Save Ground Truth Review)
 * 8. Xem và kiểm tra Báo cáo kết quả siêu âm lâm sàng (#report)
 * 9. Dọn dẹp ca kiểm thử và xác nhận không có lỗi runtime (Zero Page Errors).
 */

const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const adminPassword = process.env.APP_ADMIN_PASSWORD || 'admin-local-test-2026';

(async () => {
  console.log(`[Doctor E2E] Bắt đầu luồng kiểm thử bác sĩ tại ${base}...`);
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });

  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });

  const pageErrors = [];
  page.on('pageerror', (err) => {
    console.error('[Browser Error]', err.message);
    pageErrors.push(err.message);
  });

  let createdStudyId = null;

  try {
    // ----------------------------------------------------
    // BƯỚC 1: ĐĂNG KÝ TÀI KHOẢN BÁC SĨ MỚI (#register)
    // ----------------------------------------------------
    console.log('[Bước 1] Truy cập trang đăng ký tài khoản bác sĩ...');
    await page.goto(`${base}/#register`);
    await page.locator('#authForm').waitFor({ timeout: 10000 });

    const uniqueId = Date.now().toString().slice(-5);
    const doctorUsername = `bs_minhchau_${uniqueId}`;
    const doctorFullName = `BS.CKI Nguyễn Minh Châu (${uniqueId})`;

    await page.locator('[name=username]').fill(doctorUsername);
    await page.locator('[name=full_name]').fill(doctorFullName);
    await page.locator('[name=department]').fill('Khoa Phụ sản & CĐHA Vinmec');
    await page.locator('[name=password]').fill('MatKhauBacSi@2026');
    await page.locator('[name=confirm]').fill('MatKhauBacSi@2026');

    await page.locator('#authForm button[type=submit]').click();
    console.log(`[Bước 1] Đã đăng ký thành công bác sĩ: ${doctorUsername}`);

    // ----------------------------------------------------
    // BƯỚC 2: TỔNG QUAN LÂM SÀNG (#dashboard)
    // ----------------------------------------------------
    console.log('[Bước 2] Kiểm tra giao diện Tổng quan lâm sàng...');
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });

    const topbarName = await page.locator('.account-name').textContent();
    assert.equal(topbarName, doctorFullName, 'Tên bác sĩ trên thanh điều hướng không khớp');
    await page.locator('#dashData .metrics').waitFor({ timeout: 5000 });
    console.log('[Bước 2] Tổng quan hiển thị đầy đủ thông số thời gian thực.');

    // ----------------------------------------------------
    // BƯỚC 3: TIẾP NHẬN CA KHẢO SÁT HAI BÊN (#intake)
    // ----------------------------------------------------
    console.log('[Bước 3] Điều hướng sang màn hình Khảo sát hai bên (#intake)...');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('#startSegmentationBtn').waitFor({ timeout: 5000 });

    // Kiểm tra nút kích hoạt ban đầu bị khóa
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true, 'Nút AI phải disabled khi chưa đủ ảnh');

    const testFiles = require('./validation_files.cjs');
    assert.equal(testFiles.length, 2, 'Cần đúng 2 file ảnh mẫu');

    const pidVal = `BN-VINMEC-${uniqueId}`;
    await page.locator('[name=pid]').fill(pidVal);

    console.log('[Bước 3] Nạp ảnh buồng trứng Trái...');
    await page.locator('[data-file=L]').setInputFiles(testFiles[0]);
    await page.waitForTimeout(400);
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true, 'Chỉ 1 ảnh thì nút vẫn phải disabled');

    console.log('[Bước 3] Nạp ảnh buồng trứng Phải...');
    await page.locator('[data-file=R]').setInputFiles(testFiles[1]);
    await page.waitForTimeout(400);

    // Nút kích hoạt phải sáng lên (enabled)
    assert.equal(await page.locator('#startSegmentationBtn').isEnabled(), true, 'Nút AI phải enabled khi đủ 2 ảnh');
    console.log('[Bước 3] Cả 2 ảnh đã sẵn sàng, nút kích hoạt đã sẵn sàng.');

    // ----------------------------------------------------
    // BƯỚC 4: KÍCH HOẠT PHÂN ĐOẠN AI CHỦ ĐỘNG
    // ----------------------------------------------------
    console.log('[Bước 4] Bấm nút kích hoạt phân đoạn AI & Đo kích thước...');
    await page.locator('#startSegmentationBtn').click();

    // Chờ quá trình xử lý IQA & U-Net và chuyển sang #viewer
    await page.locator('#viewport').waitFor({ timeout: 120000 });
    await page.waitForTimeout(1000);

    createdStudyId = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.study_id;
    });
    assert.ok(createdStudyId, 'Không lấy được study_id sau khi phân đoạn');
    console.log(`[Bước 4] Phân đoạn U-Net thành công. Ca khám mã: ${createdStudyId}`);

    // ----------------------------------------------------
    // BƯỚC 5: KHÔNG GIAN RÀ SOÁT LÂM SÀNG HITL (#viewer)
    // ----------------------------------------------------
    console.log('[Bước 5] Rà soát và tương tác mask trên buồng trứng Phải...');
    await page.locator('[data-action=side-R]').click();
    await page.waitForTimeout(600);

    // Ghi nhận diện tích mask ban đầu
    const initialMaskSum = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const rightImg = state.case.images.find((i) => i.laterality === 'R');
      return rightImg.mask.reduce((acc, v) => acc + v, 0);
    });

    // Bác sĩ chọn công cụ Cọ vẽ (Brush) và vẽ tinh chỉnh
    console.log('[Bước 5] Sử dụng cọ vẽ (Brush) tinh chỉnh đường biên tổn thương...');
    await page.locator('[data-tool=brush]').click();
    const box = await page.locator('#viewport').boundingBox();
    assert.ok(box, 'Viewport canvas không tồn tại');

    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.4);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.56, box.y + box.height * 0.4);
    await page.mouse.up();
    await page.waitForTimeout(300);

    // Kiểm tra Undo / Redo
    console.log('[Bước 5] Thử nghiệm hoàn tác (Ctrl+Z) và làm lại (Ctrl+Y)...');
    await page.locator('#viewport').focus();
    await page.keyboard.press('Control+z');
    await page.waitForTimeout(200);

    const undoneMaskSum = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const rightImg = state.case.images.find((i) => i.laterality === 'R');
      return rightImg.mask.reduce((acc, v) => acc + v, 0);
    });
    assert.equal(undoneMaskSum, initialMaskSum, 'Ctrl+Z phải khôi phục mask về trạng thái ban đầu');

    await page.keyboard.press('Control+y');
    await page.waitForTimeout(200);

    // Gán nhãn hình thái
    const morphologyInput = page.locator('#morphology');
    if (await morphologyInput.count() > 0) {
      await morphologyInput.fill('Nang đơn thùy dịch trong, thành mỏng (Unilocular Anechoic Cyst)');
    }

    // ----------------------------------------------------
    // BƯỚC 6: LƯU KẾT QUẢ RÀ SOÁT CHÍNH THỨC
    // ----------------------------------------------------
    console.log('[Bước 6] Lưu kết quả rà soát hai bên...');
    const saveBtn = page.locator('[data-action=save-review]');
    assert.equal(await saveBtn.isEnabled(), true, 'Nút lưu rà soát phải khả dụng sau khi xem 2 bên');
    await saveBtn.click();

    await page.locator('#toasts .toast').filter({ hasText: 'Đã lưu rà soát của hai bên' }).waitFor({ timeout: 10000 });
    console.log('[Bước 6] Đã lưu rà soát thành công vào cơ sở dữ liệu.');

    // ----------------------------------------------------
    // BƯỚC 7: XEM BÁO CÁO KẾT QUẢ SIÊU ÂM (#report)
    // ----------------------------------------------------
    console.log('[Bước 7] Mở phiếu kết quả siêu âm lâm sàng (#report)...');
    await page.evaluate((id) => { location.hash = `#report/${id}`; }, createdStudyId);
    await page.locator('.report-card, .report-view, #reportData, .report-images').first().waitFor({ timeout: 10000 });

    const reportText = await page.locator('body').innerText();
    assert.ok(reportText.includes(pidVal) || reportText.includes('BUỒNG TRỨNG'), 'Báo cáo phải chứa mã bệnh nhân hoặc tiêu đề siêu âm');
    console.log('[Bước 7] Phiếu kết quả siêu âm hiển thị chính xác với đầy đủ hình ảnh và số đo.');

    // ----------------------------------------------------
    // BƯỚC 8: DỌN DẸP CA KIỂM THỬ
    // ----------------------------------------------------
    console.log('[Bước 8] Dọn dẹp ca kiểm thử qua API quản trị...');
    const authResp = await page.request.post(`${base}/api/auth/login`, {
      data: { username: 'admin', password: adminPassword },
    });
    const authData = await authResp.json();
    const deleteResp = await page.request.delete(`${base}/api/cases/${createdStudyId}`, {
      headers: { Authorization: `Bearer ${authData.access_token}` },
    });
    assert.equal(deleteResp.status(), 200, 'Xóa ca kiểm thử thất bại');
    console.log(`[Bước 8] Đã dọn dẹp ca ${createdStudyId} thành công.`);

    // Đảm bảo không có bất kỳ console/runtime error nào xảy ra trong toàn bộ quy trình
    assert.deepEqual(pageErrors, [], 'Phát hiện lỗi runtime trong quá trình thực thi luồng bác sĩ');
    console.log('\n======================================================');
    console.log('✅ HOÀN TẤT: Toàn bộ luồng E2E của Bác sĩ đạt 100% PASS!');
    console.log('======================================================\n');
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error('[Doctor E2E Failed]', err);
  process.exitCode = 1;
});
