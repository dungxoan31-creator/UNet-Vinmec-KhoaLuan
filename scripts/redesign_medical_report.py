import os

def main():
    before_path = 'templates/medical_report/sample_before_b64.txt'
    after_path = 'templates/medical_report/sample_after_b64.txt'

    with open(before_path, 'r', encoding='utf-8') as f:
        before_b64 = f.read().strip()
    with open(after_path, 'r', encoding='utf-8') as f:
        after_b64 = f.read().strip()

    html_content = f'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC - PHIẾU KẾT QUẢ CHẨN ĐOÁN HÌNH ẢNH</title>
  
  <!-- Vinmec Typography: Inter & JetBrains Mono for clinical clarity -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    /* ==========================================================================
       VINMEC CLINICAL REPORT DESIGN SYSTEM (PRINT & A4 OPTIMIZED)
       ========================================================================== */
    :root {{
      --vm-primary: #0068ab;
      --vm-primary-dark: #004d80;
      --vm-secondary: #008ca8;
      --vm-teal: #00a8b5;
      --vm-gold: #c59b27;
      --vm-green: #15803d;
      --vm-danger: #b91c1c;
      
      --vm-text-main: #0f172a;
      --vm-text-body: #1e293b;
      --vm-text-muted: #475569;
      --vm-text-dim: #64748b;
      
      --vm-border: #cbd5e1;
      --vm-border-light: #e2e8f0;
      --vm-bg-subtle: #f8fafc;
      --vm-bg-hover: #f1f5f9;
      
      --radius-sm: 3px;
      --radius-md: 6px;
      --radius-lg: 10px;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}

    @page {{
      size: A4 portrait;
      margin: 10mm 12mm 10mm 12mm;
    }}

    body {{
      background-color: #eaeff5;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: var(--vm-text-body);
      font-size: 9.5pt;
      line-height: 1.38;
      -webkit-font-smoothing: antialiased;
      text-rendering: geometricPrecision;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px 0 40px 0;
    }}

    /* ==========================================================================
       WEB SCREEN CONTROLS TOOLBAR (HIDDEN ON PRINT)
       ========================================================================== */
    .screen-toolbar {{
      width: 210mm;
      max-width: 100%;
      background: #ffffff;
      border: 1px solid var(--vm-border);
      border-radius: var(--radius-lg);
      padding: 10px 18px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 16px rgba(0, 50, 100, 0.08);
    }}

    .toolbar-info {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .toolbar-info h2 {{
      font-size: 13px;
      font-weight: 700;
      color: var(--vm-primary);
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .jci-tag {{
      background: var(--vm-gold);
      color: #ffffff;
      font-size: 9px;
      font-weight: 800;
      padding: 1.5px 6px;
      border-radius: 9999px;
      letter-spacing: 0.4px;
      text-transform: uppercase;
    }}

    .toolbar-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .fac-select {{
      padding: 6px 10px;
      border: 1px solid var(--vm-border);
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 600;
      color: var(--vm-primary-dark);
      background: var(--vm-bg-subtle);
      cursor: pointer;
      outline: none;
      font-family: inherit;
    }}

    .fac-select:focus {{
      border-color: var(--vm-primary);
      box-shadow: 0 0 0 2px rgba(0, 104, 171, 0.15);
    }}

    .t-btn {{
      padding: 6px 14px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-family: inherit;
      transition: all 0.15s ease;
    }}

    .t-btn-edit {{
      background: var(--vm-primary);
      color: #ffffff;
    }}
    .t-btn-edit:hover {{
      background: var(--vm-primary-dark);
    }}

    .t-btn-reset {{
      background: var(--vm-bg-subtle);
      border-color: var(--vm-border);
      color: var(--vm-text-muted);
    }}
    .t-btn-reset:hover {{
      background: var(--vm-bg-hover);
      color: var(--vm-text-main);
    }}

    .t-btn-print {{
      background: var(--vm-green);
      color: #ffffff;
    }}
    .t-btn-print:hover {{
      background: #166534;
    }}

    /* ==========================================================================
       A4 MEDICAL REPORT DOCUMENT WRAPPER (FLOW-BASED, EXACT PRINT RATIO)
       ========================================================================== */
    .report-page {{
      width: 210mm;
      min-height: 297mm;
      background: #ffffff;
      padding: 12mm 15mm 12mm 15mm;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
      position: relative;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .document-body {{
      flex: 1 0 auto;
    }}

    /* ==========================================================================
       1. HEADER (BRANDING & HOSPITAL IDENTITY)
       ========================================================================== */
    .doc-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding-bottom: 8px;
      border-bottom: 1.5px solid var(--vm-primary);
      margin-bottom: 8px;
    }}

    .header-left {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
    }}

    .logo-container {{
      width: 58px;
      flex-shrink: 0;
    }}

    .logo-svg {{
      width: 100%;
      height: auto;
      display: block;
    }}

    .hosp-info {{
      display: flex;
      flex-direction: column;
      gap: 1px;
    }}

    .hosp-name {{
      font-size: 11.5pt;
      font-weight: 800;
      color: var(--vm-primary);
      letter-spacing: -0.2px;
      line-height: 1.2;
      text-transform: uppercase;
    }}

    .dept-name {{
      font-size: 9.5pt;
      font-weight: 700;
      color: var(--vm-secondary);
      line-height: 1.2;
      margin-top: 1px;
    }}

    .hosp-meta {{
      font-size: 7.5pt;
      color: var(--vm-text-muted);
      line-height: 1.3;
      margin-top: 2px;
    }}

    .header-right {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      justify-content: center;
      flex-shrink: 0;
      padding-left: 12px;
    }}

    .qr-badge {{
      display: flex;
      flex-direction: column;
      align-items: center;
      border: 1px solid var(--vm-border);
      padding: 3px 6px;
      border-radius: var(--radius-sm);
      background: var(--vm-bg-subtle);
      text-align: center;
    }}

    .qr-badge .qr-title {{
      font-size: 6.5pt;
      font-weight: 700;
      color: var(--vm-text-dim);
      text-transform: uppercase;
    }}

    .qr-badge .rpid-text {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 8pt;
      font-weight: 700;
      color: var(--vm-text-main);
      letter-spacing: 0.3px;
    }}

    /* ==========================================================================
       2. REPORT TITLE & STUDY METADATA
       ========================================================================== */
    .title-section {{
      text-align: center;
      margin: 8px 0 10px 0;
    }}

    .report-main-title {{
      font-size: 13.5pt;
      font-weight: 800;
      color: var(--vm-primary-dark);
      letter-spacing: 0.3px;
      text-transform: uppercase;
      margin-bottom: 3px;
    }}

    .report-sub-line {{
      font-size: 8pt;
      color: var(--vm-text-muted);
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
    }}

    /* ==========================================================================
       3. PATIENT ADMINISTRATIVE TABLE (CLEAN 4-COLUMN MEDICAL GRID)
       ========================================================================== */
    .patient-grid {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 9px;
      border: 1px solid var(--vm-border-light);
      background: #ffffff;
    }}

    .patient-grid td {{
      padding: 4px 7px;
      vertical-align: middle;
      font-size: 8.8pt;
      line-height: 1.3;
      border: 1px solid var(--vm-border-light);
    }}

    .patient-grid .col-lbl {{
      color: var(--vm-text-muted);
      font-weight: 500;
      background: #fbfcfe;
      width: 18%;
      white-space: nowrap;
    }}

    .patient-grid .col-val {{
      color: var(--vm-text-main);
      font-weight: 600;
      width: 32%;
    }}

    .patient-grid .col-val.patient-name {{
      font-size: 9.5pt;
      font-weight: 800;
      color: var(--vm-primary);
      text-transform: uppercase;
    }}

    .code-font {{
      font-family: 'JetBrains Mono', monospace;
      letter-spacing: 0.2px;
    }}

    /* ==========================================================================
       4. INDICATION & TECHNIQUE SECTION
       ========================================================================== */
    .info-strip {{
      background: var(--vm-bg-subtle);
      border-left: 3px solid var(--vm-primary);
      padding: 5px 9px;
      margin-bottom: 9px;
      display: flex;
      flex-direction: column;
      gap: 2.5px;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
      border-top: 1px solid var(--vm-border-light);
      border-right: 1px solid var(--vm-border-light);
      border-bottom: 1px solid var(--vm-border-light);
    }}

    .info-strip-row {{
      display: flex;
      font-size: 8.5pt;
      line-height: 1.35;
    }}

    .info-strip-lbl {{
      width: 135px;
      flex-shrink: 0;
      font-weight: 700;
      color: var(--vm-primary-dark);
      text-transform: uppercase;
      font-size: 8pt;
    }}

    .info-strip-val {{
      flex: 1;
      color: var(--vm-text-body);
    }}

    /* ==========================================================================
       5. CLINICAL FINDINGS (MÔ TẢ HÌNH ẢNH)
       ========================================================================== */
    .section-block {{
      margin-bottom: 9px;
      page-break-inside: avoid;
    }}

    .section-head {{
      font-size: 9pt;
      font-weight: 800;
      color: var(--vm-primary);
      text-transform: uppercase;
      letter-spacing: 0.2px;
      padding-bottom: 2px;
      border-bottom: 1px solid var(--vm-border-light);
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .findings-content {{
      font-size: 8.8pt;
      line-height: 1.4;
      color: var(--vm-text-body);
    }}

    .finding-sub {{
      font-weight: 700;
      color: var(--vm-primary-dark);
      margin-top: 4px;
      margin-bottom: 1px;
      font-size: 8.8pt;
    }}

    .finding-item {{
      margin-left: 10px;
      margin-bottom: 1.5px;
      color: #1e293b;
    }}

    /* ==========================================================================
       6. ULTRASOUND IMAGE GALLERY (BEFORE / AFTER COMPARISON)
       ========================================================================== */
    .gallery-container {{
      margin-bottom: 9px;
      page-break-inside: avoid;
    }}

    .gallery-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 4px;
    }}

    .img-card {{
      border: 1px solid var(--vm-border);
      border-radius: var(--radius-sm);
      overflow: hidden;
      background: #000000;
      display: flex;
      flex-direction: column;
    }}

    .img-header {{
      background: #0f172a;
      color: #ffffff;
      padding: 3px 8px;
      font-size: 7.5pt;
      font-weight: 700;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    }}

    .img-tag-before {{
      background: #475569;
      color: #ffffff;
      font-size: 6.8pt;
      font-weight: 800;
      padding: 0.5px 4px;
      border-radius: 2px;
    }}

    .img-tag-after {{
      background: var(--vm-secondary);
      color: #ffffff;
      font-size: 6.8pt;
      font-weight: 800;
      padding: 0.5px 4px;
      border-radius: 2px;
    }}

    .img-viewport {{
      width: 100%;
      height: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #000000;
      cursor: pointer;
      overflow: hidden;
    }}

    .us-display-img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      display: block;
    }}

    .img-footer {{
      background: #f8fafc;
      border-top: 1px solid var(--vm-border-light);
      padding: 2.5px 7px;
      font-size: 7.5pt;
      color: var(--vm-text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .caliper-badge {{
      background: #e0f2fe;
      color: #0369a1;
      font-family: 'JetBrains Mono', monospace;
      font-size: 7.2pt;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 2px;
      border: 1px solid #bae6fd;
    }}

    /* ==========================================================================
       7. CONCLUSION SECTION (EMPHASIZED MEDICAL BOX)
       ========================================================================== */
    .conclusion-container {{
      border: 1.5px solid var(--vm-primary);
      border-radius: var(--radius-sm);
      background: #f8fafc;
      padding: 6px 10px;
      margin-bottom: 9px;
      page-break-inside: avoid;
    }}

    .conclusion-head {{
      font-size: 9pt;
      font-weight: 800;
      color: var(--vm-primary-dark);
      text-transform: uppercase;
      margin-bottom: 3px;
      letter-spacing: 0.2px;
    }}

    .conclusion-text-l1 {{
      font-size: 8.8pt;
      font-weight: 700;
      color: var(--vm-danger);
      line-height: 1.35;
      margin-bottom: 2px;
    }}

    .conclusion-text-l2 {{
      font-size: 8.5pt;
      font-weight: 600;
      color: var(--vm-text-main);
      line-height: 1.35;
    }}

    /* ==========================================================================
       8. SIGNATURE & STAMP BLOCK
       ========================================================================== */
    .signature-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-top: 6px;
      page-break-inside: avoid;
    }}

    .sig-meta-left {{
      font-size: 7.5pt;
      color: var(--vm-text-dim);
      max-width: 50%;
      line-height: 1.3;
    }}

    .sig-right-block {{
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 220px;
      text-align: center;
    }}

    .sig-date {{
      font-size: 8pt;
      color: var(--vm-text-muted);
      font-style: italic;
      margin-bottom: 2px;
    }}

    .sig-role {{
      font-size: 8.2pt;
      font-weight: 700;
      color: var(--vm-text-main);
      text-transform: uppercase;
    }}

    .sig-seal-box {{
      height: 40px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      margin: 2px 0;
    }}

    .digital-seal-tag {{
      border: 1px dashed var(--vm-secondary);
      background: rgba(0, 140, 168, 0.04);
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 6.8pt;
      color: var(--vm-secondary);
      font-weight: 700;
      letter-spacing: 0.2px;
    }}

    .sig-name {{
      font-size: 9.5pt;
      font-weight: 800;
      color: var(--vm-primary);
      margin-top: 1px;
    }}

    /* ==========================================================================
       9. FOOTER (JCI QUALITY & SYSTEM AUDIT)
       ========================================================================== */
    .doc-footer {{
      border-top: 1px solid var(--vm-border-light);
      padding-top: 4px;
      margin-top: 8px;
      display: flex;
      justify-content: space-between;
      font-size: 7pt;
      color: var(--vm-text-dim);
      line-height: 1.2;
    }}

    /* ==========================================================================
       PRINT OVERRIDES (@media print)
       ========================================================================== */
    @media print {{
      html, body {{
        background: #ffffff !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 210mm !important;
        height: auto !important;
      }}

      .screen-toolbar, .editor-modal {{
        display: none !important;
      }}

      .report-page {{
        width: 100% !important;
        min-height: auto !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        page-break-after: avoid;
        page-break-inside: avoid;
      }}
    }}

    /* ==========================================================================
       INTERACTIVE DATA EDITOR MODAL
       ========================================================================== */
    .editor-modal {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(3px);
      z-index: 9999;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }}

    .editor-modal.active {{
      display: flex;
    }}

    .editor-card {{
      background: #ffffff;
      width: 100%;
      max-width: 820px;
      max-height: 90vh;
      border-radius: var(--radius-lg);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      animation: modalFade 0.2s ease-out;
    }}

    @keyframes modalFade {{
      from {{ opacity: 0; transform: scale(0.97); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}

    .editor-header {{
      padding: 12px 20px;
      background: var(--vm-primary);
      color: #ffffff;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .editor-header h3 {{
      font-size: 14px;
      font-weight: 700;
    }}

    .close-btn {{
      background: none;
      border: none;
      color: #ffffff;
      font-size: 20px;
      cursor: pointer;
      line-height: 1;
      opacity: 0.85;
    }}
    .close-btn:hover {{ opacity: 1; }}

    .editor-body {{
      padding: 16px 20px;
      overflow-y: auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}

    .form-group {{
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}

    .form-group.full-width {{
      grid-column: span 2;
    }}

    .form-group.divider-head {{
      grid-column: span 2;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--vm-border-light);
    }}

    .form-group.divider-head h4 {{
      font-size: 12px;
      font-weight: 700;
      color: var(--vm-primary);
      text-transform: uppercase;
    }}

    .form-group label {{
      font-size: 11px;
      font-weight: 600;
      color: var(--vm-text-muted);
    }}

    .form-group input, .form-group textarea, .form-group select {{
      padding: 6px 9px;
      border: 1px solid var(--vm-border);
      border-radius: var(--radius-sm);
      font-size: 12px;
      color: var(--vm-text-main);
      font-family: inherit;
      background: #ffffff;
      outline: none;
    }}

    .form-group input:focus, .form-group textarea:focus, .form-group select:focus {{
      border-color: var(--vm-primary);
      box-shadow: 0 0 0 2px rgba(0, 104, 171, 0.12);
    }}

    .image-picker-box {{
      border: 1px dashed var(--vm-border);
      padding: 8px;
      border-radius: var(--radius-sm);
      background: var(--vm-bg-subtle);
      display: flex;
      flex-direction: column;
      gap: 6px;
      align-items: center;
    }}

    .preview-thumb {{
      width: 100%;
      height: 85px;
      object-fit: contain;
      background: #000000;
      border-radius: 2px;
    }}

    .editor-footer {{
      padding: 10px 20px;
      background: var(--vm-bg-subtle);
      border-top: 1px solid var(--vm-border-light);
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }}
  </style>
</head>
<body>

  <!-- 1. SCREEN TOOLBAR (WEB APP CONTROLS, HIDDEN ON PRINT) -->
  <header class="screen-toolbar">
    <div class="toolbar-info">
      <h2>🏥 BÁO CÁO KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG <span class="jci-tag">JCI ACCREDITED</span></h2>
    </div>
    <div class="toolbar-actions">
      <select id="facilitySelector" class="fac-select" onchange="onFacilityChange(this.value)">
        <option value="times_city">🏥 Vinmec Times City (Hà Nội)</option>
        <option value="ha_long">🏥 Vinmec Hạ Long (Quảng Ninh)</option>
        <option value="central_park">🏥 Vinmec Central Park (TP.HCM)</option>
        <option value="da_nang">🏥 Vinmec Đà Nẵng</option>
        <option value="hai_phong">🏥 Vinmec Hải Phòng</option>
        <option value="nha_trang">🏥 Vinmec Nha Trang</option>
        <option value="phu_quoc">🏥 Vinmec Phú Quốc</option>
      </select>
      <button class="t-btn t-btn-edit" onclick="openEditor()">📝 Chỉnh sửa dữ liệu & Ảnh</button>
      <button class="t-btn t-btn-reset" onclick="resetDefaultData()">🔄 Mẫu chuẩn</button>
      <button class="t-btn t-btn-print" onclick="window.print()">🖨️ In / Xuất PDF A4</button>
    </div>
  </header>

  <!-- 2. PHYSICAL A4 PRINT CONTAINER -->
  <main class="report-page" id="reportContent">
    <div class="document-body">

      <!-- HEADER: HOSPITAL LOGO & CONTACT -->
      <header class="doc-header">
        <div class="header-left">
          <div class="logo-container">
            <svg class="logo-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 80" version="1.1">
              <defs>
                <linearGradient x1="85.38%" y1="86.27%" x2="46.35%" y2="46.41%" id="vmGoldGrad">
                  <stop stop-color="#B57B31" offset="0%"/>
                  <stop stop-color="#F6BC2C" offset="100%"/>
                </linearGradient>
              </defs>
              <g stroke="none" stroke-width="1" fill="none" fill-rule="evenodd">
                <g fill-rule="nonzero">
                  <path d="M3.5731,48.3822 C2.9261,46.8352 2.4481,46.5252 1.4351,46.2432 C1.0131,46.1312 0.5631,46.1312 0.3381,46.1312 C0.0851,46.1312 0.0001,46.0462 0.0001,45.8782 C0.0001,45.6522 0.3101,45.6252 0.7321,45.6252 C2.2231,45.6252 3.8261,45.7092 4.8111,45.7092 C5.5141,45.7092 6.8641,45.6252 8.2711,45.6252 C8.6081,45.6252 8.9181,45.6812 8.9181,45.8782 C8.9181,46.0752 8.7491,46.1312 8.4961,46.1312 C8.0451,46.1312 7.6241,46.1592 7.3981,46.3282 C7.2011,46.4682 7.1171,46.6652 7.1171,46.9192 C7.1171,47.2842 7.3701,48.0722 7.7641,49.0852 L12.6031,61.8562 L12.7151,61.8562 C13.9251,58.7622 17.5821,49.7042 18.2571,47.8472 C18.3981,47.4812 18.5101,47.0592 18.5101,46.8062 C18.5101,46.5812 18.3981,46.3562 18.1451,46.2712 C17.8071,46.1592 17.3851,46.1312 17.0191,46.1312 C16.7661,46.1312 16.5411,46.1032 16.5411,45.9062 C16.5411,45.6812 16.7941,45.6252 17.3291,45.6252 C18.7351,45.6252 19.9171,45.7092 20.2831,45.7092 C20.7611,45.7092 22.0831,45.6252 22.9271,45.6252 C23.2931,45.6252 23.5181,45.6812 23.5181,45.8782 C23.5181,46.0752 23.3491,46.1312 23.0681,46.1312 C22.7861,46.1312 22.1961,46.1312 21.6891,46.4682 C21.3231,46.7222 20.9021,47.2002 20.1421,49.0012 C19.0451,51.6452 18.2851,53.1642 16.7661,56.6242 C14.9661,60.7312 13.6441,63.7972 13.0251,65.2042 C12.2931,66.8352 12.1241,67.2862 11.7311,67.2862 C11.3651,67.2862 11.1961,66.8922 10.6621,65.5702 L3.5731,48.3822 Z" fill="#0068ab"/>
                  <path d="M26.8062,55.7243 C26.8062,52.0943 26.8062,51.4193 26.7782,50.6603 C26.7222,49.8443 26.4682,49.5633 25.9342,49.3943 C25.6532,49.3103 25.3432,49.2823 25.0342,49.2823 C24.7812,49.2823 24.6402,49.2253 24.6402,49.0013 C24.6402,48.8603 24.8372,48.8043 25.2312,48.8043 C26.1592,48.8043 27.8472,48.8603 28.5502,48.8603 C29.1692,48.8603 30.7732,48.8043 31.7292,48.8043 C32.0382,48.8043 32.2352,48.8603 32.2352,49.0013 C32.2352,49.2253 32.0952,49.2823 31.8412,49.2823 C31.5882,49.2823 31.3912,49.3103 31.1102,49.3663 C30.4352,49.4793 30.2382,49.8163 30.1822,50.6603 C30.1262,51.4193 30.1262,52.0943 30.1262,55.7243 L30.1262,59.9443 C30.1262,62.2503 30.1262,64.1633 30.2382,65.1763 C30.3232,65.8223 30.4912,66.1893 31.2232,66.3013 C31.5602,66.3573 32.1232,66.3863 32.4892,66.3863 C32.7702,66.3863 32.8822,66.5263 32.8822,66.6383 C32.8822,66.8073 32.6852,66.8923 32.4042,66.8923 C30.7732,66.8923 29.0852,66.8073 28.4092,66.8073 C27.8472,66.8073 26.1592,66.8923 25.1742,66.8923 C24.8652,66.8923 24.6962,66.8073 24.6962,66.6383 C24.6962,66.5263 24.7812,66.3863 25.0902,66.3863 C25.4562,66.3863 25.7372,66.3573 25.9622,66.3013 C26.4682,66.1893 26.6092,65.8513 26.6942,65.1473 C26.8062,64.1633 26.8062,62.2503 26.8062,59.9443 L26.8062,55.7243 Z" fill="#0068ab"/>
                  <path d="M41.1795,63.6287 C41.2355,65.4847 41.5455,66.0487 42.0235,66.2167 C42.4455,66.3577 42.9235,66.3857 43.3175,66.3857 C43.5985,66.3857 43.7395,66.4977 43.7395,66.6387 C43.7395,66.8357 43.5145,66.8917 43.1765,66.8917 C41.5735,66.8917 40.4195,66.8077 39.9695,66.8077 C39.7445,66.8077 38.5635,66.8917 37.2975,66.8917 C36.9595,66.8917 36.7345,66.8647 36.7345,66.6387 C36.7345,66.4977 36.9035,66.3857 37.1285,66.3857 C37.4655,66.3857 37.9165,66.2727 38.2535,66.2727 C38.9005,66.1037 38.9855,65.4577 39.0135,63.3757 L39.2385,49.1977 C39.2385,48.7197 39.4075,48.3817 39.6605,48.3817 C39.9695,48.3817 40.3075,48.7477 40.7295,49.1697 C41.0385,49.4787 44.7525,53.2767 48.3525,56.7927 C50.0405,58.4527 53.3325,61.8277 53.6975,62.1657 L53.8105,62.1657 L53.5565,51.5327 C53.5285,50.0687 53.3035,49.6477 52.7125,49.4227 C52.3475,49.2817 51.7565,49.2817 51.4185,49.2817 C51.1095,49.2817 51.0255,49.1697 51.0255,49.0287 C51.0255,48.8317 51.2785,48.8037 51.6445,48.8037 C52.9385,48.8037 54.2605,48.8607 54.7945,48.8607 C55.0765,48.8607 56.0045,48.8037 57.2145,48.8037 C57.5515,48.8037 57.7765,48.8317 57.7765,49.0287 C57.7765,49.1697 57.6355,49.2817 57.3545,49.2817 C57.1015,49.2817 56.9045,49.2817 56.5955,49.3667 C55.9205,49.5637 55.7235,49.9847 55.6945,51.3357 L55.4135,66.4137 C55.4135,66.9487 55.2165,67.1727 55.0195,67.1727 C54.5975,67.1727 54.2605,66.9197 54.0065,66.6667 C52.4605,65.2327 49.3655,62.2787 46.7775,59.7747 C44.0765,57.1867 41.4605,54.2887 40.9825,53.8667 L40.8985,53.8667 L41.1795,63.6287 Z" fill="#0068ab"/>
                  <path d="M66.2967,45.7377 C66.3817,45.2597 66.5497,45.0057 66.7757,45.0057 C66.9997,45.0057 67.1687,45.1467 67.5347,45.8787 L75.2147,61.7437 L82.8657,45.6817 C83.0917,45.2307 83.2317,45.0057 83.4847,45.0057 C83.7387,45.0057 83.9067,45.2877 83.9907,45.8787 L86.5517,63.2637 C86.8047,65.0357 87.0857,65.8517 87.9297,66.1037 C88.7457,66.3577 89.3087,66.3857 89.6737,66.3857 C89.9267,66.3857 90.1237,66.4137 90.1237,66.5817 C90.1237,66.8077 89.7867,66.8917 89.3927,66.8917 C88.6897,66.8917 84.8067,66.8077 83.6817,66.7237 C83.0347,66.6667 82.8657,66.5817 82.8657,66.4137 C82.8657,66.2727 82.9787,66.1887 83.1757,66.1037 C83.3447,66.0487 83.4287,65.6817 83.3157,64.8947 L81.6287,52.5167 L81.5157,52.5167 L75.3837,65.2877 C74.7367,66.6107 74.5957,66.8637 74.3427,66.8637 C74.0897,66.8637 73.8077,66.3007 73.3577,65.4577 C72.6827,64.1637 70.4607,59.8587 70.1227,59.0717 C69.8697,58.4807 68.1817,54.9357 67.1967,52.8267 L67.0847,52.8267 L65.6217,64.0227 C65.5657,64.5287 65.5377,64.8947 65.5377,65.3447 C65.5377,65.8787 65.9027,66.1327 66.3817,66.2447 C66.8877,66.3577 67.2817,66.3857 67.5627,66.3857 C67.7877,66.3857 67.9847,66.4417 67.9847,66.5817 C67.9847,66.8357 67.7317,66.8917 67.3097,66.8917 C66.1277,66.8917 64.8617,66.8077 64.3557,66.8077 C63.8217,66.8077 62.4717,66.8917 61.5707,66.8917 C61.2897,66.8917 61.0647,66.8357 61.0647,66.5817 C61.0647,66.4417 61.2327,66.3857 61.5147,66.3857 C61.7397,66.3857 61.9367,66.3857 62.3587,66.3007 C63.1467,66.1327 63.3707,65.0357 63.5117,64.0787 L66.2967,45.7377 Z" fill="#0068ab"/>
                  <path d="M95.4082,55.7243 C95.4082,52.0943 95.4082,51.4193 95.3802,50.6603 C95.3242,49.8443 95.0992,49.5913 94.3112,49.3663 C94.1142,49.3103 93.6922,49.2823 93.3262,49.2823 C93.0732,49.2823 92.9052,49.1983 92.9052,49.0283 C92.9052,48.8603 93.1012,48.8043 93.4672,48.8043 C94.7612,48.8043 96.3372,48.8603 97.0402,48.8603 C97.8272,48.8603 103.3132,48.8883 103.7912,48.8603 C104.2412,48.8313 104.6352,48.7473 104.8322,48.7193 C104.9732,48.6913 105.1132,48.6073 105.2262,48.6073 C105.3662,48.6073 105.3952,48.7193 105.3952,48.8313 C105.3952,49.0013 105.2542,49.2823 105.1972,50.3793 C105.1702,50.6323 105.1132,51.6733 105.0572,51.9543 C105.0292,52.0673 104.9732,52.3483 104.7762,52.3483 C104.6072,52.3483 104.5792,52.2353 104.5792,52.0383 C104.5792,51.8703 104.5512,51.4483 104.4102,51.1673 C104.2132,50.7443 104.0162,50.4063 102.7782,50.2953 C102.3572,50.2383 99.4032,50.1823 98.8962,50.1823 C98.7842,50.1823 98.7282,50.2663 98.7282,50.4063 L98.7282,56.3143 C98.7282,56.4553 98.7562,56.5683 98.8962,56.5683 C99.4592,56.5683 102.6662,56.5683 103.2282,56.5113 C103.8192,56.4553 104.1852,56.3993 104.4102,56.1463 C104.6072,55.9763 104.6922,55.8363 104.8042,55.8363 C104.9162,55.8363 105.0012,55.9493 105.0012,56.0893 C105.0012,56.2303 104.9452,56.6243 104.8042,57.8343 C104.7482,58.3123 104.6922,59.2683 104.6922,59.4373 C104.6922,59.6343 104.6632,59.9713 104.4382,59.9713 C104.2692,59.9713 104.2132,59.8873 104.2132,59.7743 C104.1852,59.5223 104.1852,59.2123 104.1292,58.9023 C103.9882,58.4243 103.6792,58.0593 102.7502,57.9743 C102.3002,57.9183 99.4872,57.8613 98.8682,57.8613 C98.7562,57.8613 98.7282,57.9743 98.7282,58.1153 L98.7282,60.0283 C98.7282,60.8443 98.6992,62.8693 98.7282,63.5723 C98.7842,65.2043 99.5432,65.5703 102.0752,65.5703 C102.7222,65.5703 103.7632,65.5413 104.4102,65.2603 C105.0292,64.9793 105.3102,64.4723 105.4792,63.4883 C105.5352,63.2343 105.5922,63.1233 105.7602,63.1233 C105.9572,63.1233 105.9862,63.4313 105.9862,63.6853 C105.9862,64.2203 105.7892,65.8513 105.6482,66.3293 C105.4792,66.9483 105.2542,66.9483 104.3262,66.9483 C102.4692,66.9483 100.9782,66.9193 99.7692,66.8643 C98.5592,66.8353 97.6312,66.8073 96.8992,66.8073 C96.6182,66.8073 96.0832,66.8353 95.4932,66.8353 C94.9022,66.8643 94.2832,66.8923 93.7762,66.8923 C93.4672,66.8923 93.2982,66.8073 93.2982,66.6383 C93.2982,66.5263 93.3832,66.3863 93.6922,66.3863 C94.0582,66.3863 94.3392,66.3573 94.5642,66.3013 C95.0702,66.1893 95.2112,65.7383 95.2962,65.0353 C95.4082,64.0223 95.4082,62.1373 95.4082,59.9443 L95.4082,55.7243 Z" fill="#0068ab"/>
                  <path d="M113.4095,64.6128 C110.9625,62.5598 110.3155,59.8588 110.3155,57.5528 C110.3155,55.9208 110.8495,53.1078 113.2125,50.9978 C115.0125,49.4228 117.3765,48.4658 121.0615,48.4658 C122.6085,48.4658 123.5365,48.5778 124.6615,48.7198 C125.5895,48.8608 126.4055,49.0288 127.1375,49.1128 C127.4185,49.1418 127.5035,49.2538 127.5035,49.3938 C127.5035,49.5908 127.4465,49.8718 127.3905,50.7168 C127.3345,51.5038 127.3345,52.8268 127.3065,53.3048 C127.2775,53.6418 127.1935,53.8958 126.9685,53.8958 C126.7715,53.8958 126.7155,53.6988 126.7155,53.3888 C126.6875,52.6298 126.3785,51.7858 125.7585,51.1668 C124.9155,50.3518 123.2555,49.7598 120.9765,49.7598 C118.8105,49.7598 117.4315,50.1548 116.3065,51.1108 C114.4785,52.6858 114.0285,54.9928 114.0285,57.3268 C114.0285,63.0098 118.4165,65.7108 121.7365,65.7108 C123.9305,65.7108 125.1395,65.5418 126.1245,64.4448 C126.5465,63.9668 126.8845,63.2908 126.9685,62.8408 C127.0245,62.4748 127.0805,62.3628 127.2775,62.3628 C127.4465,62.3628 127.5595,62.5878 127.5595,62.7848 C127.5595,63.0668 127.2775,65.1478 127.0245,65.9628 C126.9125,66.3858 126.7995,66.4978 126.3785,66.6668 C125.3935,67.0598 123.5085,67.2018 121.9055,67.2018 C118.5295,67.2018 115.6595,66.4978 113.4095,64.6128" fill="#0068ab"/>
                  <path d="M78.736,0.431 C69.473,1.612 60.141,4.786 59.515,14.118 L59.515,14.118 C59.218,18.552 60.567,21.882 62.092,25.091 L62.092,25.091 C58.269,21.288 52.751,18.243 45.009,18.984 L45.009,18.984 C49.72,20.334 55.285,22.916 58.274,26.332 L58.274,26.332 C58.906,27.056 59.827,28.309 59.608,29.386 L59.608,29.386 C59.249,31.188 55.967,30.82 53.98,30.913 L53.98,30.913 C58.102,32.583 62.706,35.591 68.579,35.397 L68.579,35.397 C71.519,35.301 73.677,33.496 73.446,30.15 L73.446,30.15 C73.039,24.138 68.656,19.003 68.199,12.209 L68.199,12.209 C67.69,4.65 72.867,1.808 78.746,0.523 L78.746,0.523 C78.777,0.515 79.363,0.401 79.297,0.387 L79.297,0.387 C79.295,0.387 79.291,0.386 79.285,0.386 L79.285,0.386 C79.204,0.386 78.795,0.423 78.736,0.431" fill="url(#vmGoldGrad)"/>
                </g>
              </g>
            </svg>
          </div>
          <div class="hosp-info">
            <h1 class="hosp-name" id="field_hospitalName">BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY</h1>
            <div class="dept-name" id="field_departmentName">KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA</div>
            <div class="hosp-meta">
              <span id="field_hospitalAddress">Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội</span><br>
              <span id="field_hospitalContact">Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333</span>
            </div>
          </div>
        </div>
        <div class="header-right">
          <div class="qr-badge">
            <span class="qr-title">MÃ PHIẾU / RPID</span>
            <span class="rpid-text" id="field_rpid">HAN26652307901</span>
          </div>
        </div>
      </header>

      <!-- TITLE SECTION -->
      <section class="title-section">
        <h2 class="report-main-title" id="field_reportTitle">PHIẾU KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG & TIỂU KHUNG</h2>
        <div class="report-sub-line">
          <span>Thời gian chỉ định: <strong class="code-font" id="field_orderDate">26-Aug-2026 10:42 AM</strong></span>
          <span>•</span>
          <span>Thời gian thực hiện: <strong class="code-font" id="field_completedDate">26-Aug-2026 11:07 AM</strong></span>
        </div>
      </section>

      <!-- PATIENT ADMINISTRATIVE GRID -->
      <table class="patient-grid">
        <tr>
          <td class="col-lbl">Họ và tên người bệnh:</td>
          <td class="col-val patient-name" id="field_patientName">Nguyễn Thị Phượng</td>
          <td class="col-lbl">Mã người bệnh (PID):</td>
          <td class="col-val code-font" id="field_patientId">200044962</td>
        </tr>
        <tr>
          <td class="col-lbl">Ngày sinh:</td>
          <td class="col-val code-font" id="field_patientDob">16/05/1991</td>
          <td class="col-lbl">Giới tính:</td>
          <td class="col-val" id="field_patientGender">Nữ (Female)</td>
        </tr>
        <tr>
          <td class="col-lbl">Bác sĩ chỉ định:</td>
          <td class="col-val" id="field_referringDoctor">TS. BS. Lê Khắc Hiếu</td>
          <td class="col-lbl">Đối tượng / Lượt khám:</td>
          <td class="col-val" id="field_visitType">Khám ngoại trú (OPD) / 3090373</td>
        </tr>
        <tr>
          <td class="col-lbl">Dịch vụ:</td>
          <td class="col-val" colspan="3" id="field_serviceName">Khám chuyên khoa Phụ khoa — Siêu âm Đầu dò</td>
        </tr>
      </table>

      <!-- INDICATION & TECHNIQUE STRIP -->
      <section class="info-strip">
        <div class="info-strip-row">
          <span class="info-strip-lbl">Tên chỉ định:</span>
          <span class="info-strip-val" style="font-weight:700;" id="field_orderName">Siêu âm buồng trứng qua ngả âm đạo [Đánh giá khối u nang bằng AI Attention U-Net]</span>
        </div>
        <div class="info-strip-row">
          <span class="info-strip-lbl">Chẩn đoán lâm sàng:</span>
          <span class="info-strip-val" id="field_clinicalDiagnosis">Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị</span>
        </div>
        <div class="info-strip-row">
          <span class="info-strip-lbl">Kỹ thuật thực hiện:</span>
          <span class="info-strip-val" id="field_technique">Siêu âm 2D Doppler màu ngả âm đạo kết hợp mô hình AI Attention U-Net tự động phân đoạn ranh giới u và trích xuất kích thước trực giao (D1, D2, Diện tích).</span>
        </div>
      </section>

      <!-- CLINICAL DESCRIPTION -->
      <section class="section-block">
        <div class="section-head">
          <span>MÔ TẢ HÌNH ẢNH SIÊU ÂM</span>
        </div>
        <div class="findings-content">
          <div class="finding-sub">1. BUỒNG TRỨNG PHẢI:</div>
          <div class="finding-item" id="field_ovary_r1">- Kích thước buồng trứng: 38 x 26 mm. Vị trí tiếp giáp bình thường.</div>
          <div class="finding-item" id="field_ovary_r2">- Tổn thương: Bên trong phát hiện 01 cấu trúc dạng u nang, ranh giới rõ, thành mỏng đều.</div>
          <div class="finding-item" id="field_ovary_r3">- Đo đạc AI (Attention U-Net): Đường kính lớn nhất D1 = 28.5 mm, Đường kính trực giao D2 = 21.0 mm, Diện tích = 4.62 cm².</div>
          <div class="finding-item" id="field_ovary_r4">- Doppler màu: Không thấy tăng sinh mạch máu bất thường trong vách hoặc thành nang (RI = 0.62).</div>

          <div class="finding-sub">2. BUỒNG TRỨNG TRÁI:</div>
          <div class="finding-item" id="field_ovary_l1">- Kích thước buồng trứng: 26 x 18 mm. Nhu mô đồng nhất. Các nang noãn sinh lý &lt; 8 mm rải rác ở ngoại vi, không thấy cấu trúc u cục khu trú hay nang bất thường.</div>

          <div class="finding-sub">3. TÚI CÙNG DOUGLAS & TIỂU KHUNG:</div>
          <div class="finding-item" id="field_douglas">- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.</div>
        </div>
      </section>

      <!-- BEFORE / AFTER ULTRASOUND GALLERY -->
      <section class="gallery-container">
        <div class="section-head">
          <span>HÌNH ẢNH SIÊU ÂM MINH HỌA</span>
          <span style="font-size:7.2pt; color:var(--vm-text-dim); text-transform:none; font-weight:600;">Hỗ trợ phân đoạn: Attention U-Net Deep Learning (Độ tin cậy: 96.4%)</span>
        </div>
        <div class="gallery-grid">
          <!-- BEFORE: RAW IMAGE -->
          <div class="img-card">
            <div class="img-header">
              <span>ẢNH SIÊU ÂM GỐC (B-MODE)</span>
              <span class="img-tag-before">BEFORE</span>
            </div>
            <div class="img-viewport" onclick="openImageZoom('before')" title="Click để phóng to ảnh gốc">
              <img id="field_imageBefore" class="us-display-img" src="{before_b64}" alt="Ảnh siêu âm gốc">
            </div>
            <div class="img-footer">
              <span id="field_imageBeforeCaption">Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)</span>
              <span style="font-weight:700; color:var(--vm-primary);">RAW B-MODE</span>
            </div>
          </div>

          <!-- AFTER: AI OVERLAY -->
          <div class="img-card">
            <div class="img-header">
              <span>ẢNH PHÂN ĐOẠN AI & CALIPERS</span>
              <span class="img-tag-after">AFTER</span>
            </div>
            <div class="img-viewport" onclick="openImageZoom('after')" title="Click để phóng to ảnh phân đoạn AI">
              <img id="field_imageAfter" class="us-display-img" src="{after_b64}" alt="Ảnh phân đoạn AI">
            </div>
            <div class="img-footer">
              <span class="caliper-badge" id="field_imageCaliperTag">D1: 28.5 mm • D2: 21.0 mm • DT: 4.62 cm²</span>
              <span style="font-weight:700; color:var(--vm-green);">96.4% CONF</span>
            </div>
          </div>
        </div>
      </section>

      <!-- CONCLUSION BLOCK -->
      <section class="conclusion-container">
        <div class="conclusion-head">KẾT LUẬN</div>
        <p class="conclusion-text-l1" id="field_conclusion_l1">1. HÌNH ẢNH U NANG BUỒNG TRỨNG PHẢI (THEO DÕI U BÌ / U NANG THANH DỊCH - PHÂN LOẠI O-RADS 2).</p>
        <p class="conclusion-text-l2" id="field_conclusion_l2">2. BUỒNG TRỨNG TRÁI VÀ CÙNG ĐỒ DOUGLAS HIỆN TẠI TRONG GIỚI HẠN BÌNH THƯỜNG. ĐỀ NGHỊ SIÊU ÂM KIỂM TRA LẠI SAU 3 THÁNG.</p>
      </section>

      <!-- SIGNATURE AND DOCTOR APPROVAL -->
      <section class="signature-row">
        <div class="sig-meta-left">
          <span>* Kết quả chẩn đoán hình ảnh này là căn cứ y khoa quan trọng. Người bệnh vui lòng mang theo kết quả khi tái khám hoặc hội chẩn chuyên khoa.</span>
        </div>
        <div class="sig-right-block">
          <div class="sig-date">Hà Nội, ngày 26 tháng 08 năm 2026</div>
          <div class="sig-role" id="field_doctorTitle">Bác sĩ chuyên khoa Chẩn đoán hình ảnh</div>
          <div class="sig-seal-box">
            <span class="digital-seal-tag">✓ ĐÃ KÝ ĐIỆN TỬ (VINMEC HIS)</span>
          </div>
          <div class="sig-name" id="field_doctorName">BS.CKII. Trương Thị Phượng</div>
        </div>
      </section>
    </div>

    <!-- FOOTER -->
    <footer class="doc-footer">
      <div id="field_footerApprovedBy">Kết quả đã được duyệt bởi: BS.CKII. Trương Thị Phượng — Hệ thống AI Decision Support v1.2</div>
      <div>Hệ thống Y tế Vinmec đạt chuẩn kiểm định chất lượng JCI Hoa Kỳ | Trang 1/1</div>
    </footer>
  </main>

  <!-- 3. LIVE DATA & IMAGE EDITOR MODAL -->
  <div class="editor-modal" id="editorModal">
    <div class="editor-card">
      <div class="editor-header">
        <h3>📝 CHỈNH SỬA THÔNG TIN & HÌNH ẢNH BÁO CÁO Y KHOA</h3>
        <button class="close-btn" onclick="closeEditor()" title="Đóng">×</button>
      </div>
      <div class="editor-body">
        <div class="form-group full-width">
          <label>Cơ sở Bệnh viện Đa khoa Quốc tế Vinmec:</label>
          <select id="modal_facilitySelector" onchange="onModalFacilityChange(this.value)">
            <option value="times_city">Vinmec Times City (Hà Nội)</option>
            <option value="ha_long">Vinmec Hạ Long (Quảng Ninh)</option>
            <option value="central_park">Vinmec Central Park (TP.HCM)</option>
            <option value="da_nang">Vinmec Đà Nẵng</option>
            <option value="hai_phong">Vinmec Hải Phòng</option>
            <option value="nha_trang">Vinmec Nha Trang</option>
            <option value="phu_quoc">Vinmec Phú Quốc</option>
          </select>
        </div>

        <!-- IMAGE CONTROLS -->
        <div class="form-group divider-head">
          <h4>🖼️ HÌNH ẢNH SIÊU ÂM (BEFORE & AFTER)</h4>
        </div>

        <div class="form-group">
          <label>Ảnh siêu âm gốc (Before - B-Mode):</label>
          <div class="image-picker-box">
            <img id="modal_preview_before" class="preview-thumb" src="{before_b64}" alt="Preview Before">
            <input type="file" id="upload_imageBefore" accept="image/*" onchange="handleImageUpload(event, 'before')">
          </div>
        </div>

        <div class="form-group">
          <label>Ảnh phân đoạn AI (After - Overlay & Calipers):</label>
          <div class="image-picker-box">
            <img id="modal_preview_after" class="preview-thumb" src="{after_b64}" alt="Preview After">
            <input type="file" id="upload_imageAfter" accept="image/*" onchange="handleImageUpload(event, 'after')">
          </div>
        </div>

        <div class="form-group">
          <label>Chú thích ảnh gốc (Before Caption):</label>
          <input type="text" id="input_imageBeforeCaption" placeholder="Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)">
        </div>

        <div class="form-group">
          <label>Thẻ số đo Calipers (After Chip):</label>
          <input type="text" id="input_imageCaliperTag" placeholder="D1: 28.5 mm • D2: 21.0 mm • DT: 4.62 cm²">
        </div>

        <!-- PATIENT ADMINISTRATIVE DATA -->
        <div class="form-group divider-head">
          <h4>👤 THÔNG TIN NGƯỜI BỆNH & CHỈ ĐỊNH</h4>
        </div>

        <div class="form-group">
          <label>Mã người bệnh (PID):</label>
          <input type="text" id="input_patientId">
        </div>
        <div class="form-group">
          <label>Họ và tên người bệnh:</label>
          <input type="text" id="input_patientName">
        </div>
        <div class="form-group">
          <label>Giới tính:</label>
          <input type="text" id="input_patientGender">
        </div>
        <div class="form-group">
          <label>Ngày sinh:</label>
          <input type="text" id="input_patientDob">
        </div>
        <div class="form-group">
          <label>Ngày chỉ định:</label>
          <input type="text" id="input_orderDate">
        </div>
        <div class="form-group">
          <label>Đối tượng / Lượt khám:</label>
          <input type="text" id="input_visitType">
        </div>
        <div class="form-group">
          <label>Bác sĩ chỉ định:</label>
          <input type="text" id="input_referringDoctor">
        </div>
        <div class="form-group">
          <label>Dịch vụ khám:</label>
          <input type="text" id="input_serviceName">
        </div>
        <div class="form-group full-width">
          <label>Tên chỉ định siêu âm:</label>
          <input type="text" id="input_orderName">
        </div>
        <div class="form-group">
          <label>Ngày hoàn thành chỉ định:</label>
          <input type="text" id="input_completedDate">
        </div>
        <div class="form-group">
          <label>Mã RPID:</label>
          <input type="text" id="input_rpid">
        </div>
        <div class="form-group full-width">
          <label>Chẩn đoán lâm sàng:</label>
          <input type="text" id="input_clinicalDiagnosis">
        </div>
        <div class="form-group full-width">
          <label>Kỹ thuật thực hiện:</label>
          <input type="text" id="input_technique">
        </div>

        <!-- FINDINGS & CONCLUSION -->
        <div class="form-group divider-head">
          <h4>🔬 MÔ TẢ HÌNH ẢNH & KẾT LUẬN</h4>
        </div>

        <div class="form-group full-width">
          <label>Buồng trứng phải (Dòng 1 - Kích thước):</label>
          <input type="text" id="input_ovary_r1">
        </div>
        <div class="form-group full-width">
          <label>Buồng trứng phải (Dòng 2 - Tổn thương):</label>
          <input type="text" id="input_ovary_r2">
        </div>
        <div class="form-group full-width">
          <label>Buồng trứng phải (Dòng 3 - Số đo AI D1, D2, Diện tích):</label>
          <input type="text" id="input_ovary_r3">
        </div>
        <div class="form-group full-width">
          <label>Buồng trứng phải (Dòng 4 - Doppler mạch máu):</label>
          <input type="text" id="input_ovary_r4">
        </div>
        <div class="form-group full-width">
          <label>Buồng trứng trái (Mô tả & nang noãn):</label>
          <input type="text" id="input_ovary_l1">
        </div>
        <div class="form-group full-width">
          <label>Túi cùng Douglas & Dịch tiểu khung:</label>
          <input type="text" id="input_douglas">
        </div>
        <div class="form-group full-width">
          <label>Kết luận chẩn đoán (Dòng 1 - O-RADS):</label>
          <input type="text" id="input_conclusion_l1">
        </div>
        <div class="form-group full-width">
          <label>Kết luận chẩn đoán (Dòng 2 - Khuyến nghị theo dõi):</label>
          <input type="text" id="input_conclusion_l2">
        </div>
        <div class="form-group">
          <label>Chức danh bác sĩ:</label>
          <input type="text" id="input_doctorTitle">
        </div>
        <div class="form-group">
          <label>Tên bác sĩ ký duyệt:</label>
          <input type="text" id="input_doctorName">
        </div>
      </div>
      <div class="editor-footer">
        <button class="t-btn t-btn-reset" onclick="closeEditor()">Hủy</button>
        <button class="t-btn t-btn-edit" onclick="applyEditorData()">Cập nhật Báo Cáo</button>
      </div>
    </div>
  </div>

  <script>
    // DANH MỤC CƠ SỞ Y TẾ VINMEC
    const VINMEC_FACILITIES = {{
      times_city: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
        hospitalContact: "Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333"
      }},
      ha_long: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẠ LONG",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Số 10A, đường Lê Thánh Tông, Phường Hồng Gai, Tỉnh Quảng Ninh, Việt Nam",
        hospitalContact: "Tel: +84 (203) 3828188 | Hotline: +84 (203) 3656115 | Cấp cứu: +84 (203) 3511599"
      }},
      central_park: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC CENTRAL PARK",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Số 208 Nguyễn Hữu Cảnh, Phường 22, Quận Bình Thạnh, TP. Hồ Chí Minh",
        hospitalContact: "Tel: +84 (28) 3622 1166 | Hotline: +84 (28) 3622 1188 | Cấp cứu: +84 (28) 3622 9999"
      }},
      da_nang: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC ĐÀ NẴNG",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Đường 30 Tháng 4, Khu dân cư số 4 Nguyễn Tri Phương, Phường Hòa Cường Bắc, Quận Hải Châu, Đà Nẵng",
        hospitalContact: "Tel: +84 (236) 3711 111 | Hotline: +84 (236) 3711 113 | Cấp cứu: +84 (236) 3611 611"
      }},
      hai_phong: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC HẢI PHÒNG",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Đường Võ Nguyên Giáp, Phường Vĩnh Niệm, Quận Lê Chân, Hải Phòng",
        hospitalContact: "Tel: +84 (225) 7309 888 | Hotline: +84 (225) 7309 890 | Cấp cứu: +84 (225) 7309 115"
      }},
      nha_trang: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC NHA TRANG",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Số 42A Trần Phú, Phường Vĩnh Nguyên, TP. Nha Trang, Tỉnh Khánh Hòa",
        hospitalContact: "Tel: +84 (258) 3900 168 | Hotline: +84 (258) 3900 170 | Cấp cứu: +84 (258) 3900 115"
      }},
      phu_quoc: {{
        hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC PHÚ QUỐC",
        departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: "Địa chỉ: Bãi Dài, Xã Gành Dầu, Thành phố Phú Quốc, Tỉnh Kiên Giang",
        hospitalContact: "Tel: +84 (297) 398 5588 | Hotline: +84 (297) 398 5590 | Cấp cứu: +84 (297) 398 5115"
      }}
    }};

    // DỮ LIỆU GỐC CHUYÊN BIỆT BUỒNG TRỨNG
    const DEFAULT_DATA = {{
      facilityKey: "times_city",
      hospitalName: "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
      departmentName: "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
      hospitalAddress: "Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
      hospitalContact: "Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333",
      reportTitle: "PHIẾU KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG & TIỂU KHUNG",
      patientId: "200044962",
      patientName: "Nguyễn Thị Phượng",
      patientGender: "Nữ (Female)",
      patientDob: "16/05/1991",
      orderDate: "26-Aug-2026 10:42 AM",
      visitType: "Khám ngoại trú (OPD) / 3090373",
      referringDoctor: "TS. BS. Lê Khắc Hiếu",
      serviceName: "Khám chuyên khoa Phụ khoa — Siêu âm Đầu dò",
      orderName: "Siêu âm buồng trứng qua ngả âm đạo [Đánh giá khối u nang bằng AI Attention U-Net]",
      completedDate: "26-Aug-2026 11:07 AM",
      rpid: "HAN26652307901",
      clinicalDiagnosis: "Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị",
      technique: "Siêu âm 2D Doppler màu ngả âm đạo kết hợp mô hình AI Attention U-Net tự động phân đoạn ranh giới u và trích xuất kích thước trực giao (D1, D2, Diện tích).",
      ovary_r1: "- Kích thước buồng trứng: 38 x 26 mm. Vị trí tiếp giáp bình thường.",
      ovary_r2: "- Tổn thương: Bên trong phát hiện 01 cấu trúc dạng u nang, ranh giới rõ, thành mỏng đều.",
      ovary_r3: "- Đo đạc AI (Attention U-Net): Đường kính lớn nhất D1 = 28.5 mm, Đường kính trực giao D2 = 21.0 mm, Diện tích = 4.62 cm².",
      ovary_r4: "- Doppler màu: Không thấy tăng sinh mạch máu bất thường trong vách hoặc thành nang (RI = 0.62).",
      ovary_l1: "- Kích thước buồng trứng: 26 x 18 mm. Nhu mô đồng nhất. Các nang noãn sinh lý < 8 mm rải rác ở ngoại vi, không thấy cấu trúc u cục khu trú hay nang bất thường.",
      douglas: "- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.",
      conclusion_l1: "1. HÌNH ẢNH U NANG BUỒNG TRỨNG PHẢI (THEO DÕI U BÌ / U NANG THANH DỊCH - PHÂN LOẠI O-RADS 2).",
      conclusion_l2: "2. BUỒNG TRỨNG TRÁI VÀ CÙNG ĐỒ DOUGLAS HIỆN TẠI TRONG GIỚI HẠN BÌNH THƯỜNG. ĐỀ NGHỊ SIÊU ÂM KIỂM TRA LẠI SAU 3 THÁNG.",
      doctorTitle: "Bác sĩ chuyên khoa Chẩn đoán hình ảnh",
      doctorName: "BS.CKII. Trương Thị Phượng",
      footerApprovedBy: "Kết quả đã được duyệt bởi: BS.CKII. Trương Thị Phượng — Hệ thống AI Decision Support v1.2",
      imageBefore: "{before_b64}",
      imageAfter: "{after_b64}",
      imageBeforeCaption: "Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)",
      imageCaliperTag: "D1: 28.5 mm • D2: 21.0 mm • DT: 4.62 cm²"
    }};

    let currentReportData = JSON.parse(JSON.stringify(DEFAULT_DATA));
    let tempImageBefore = DEFAULT_DATA.imageBefore;
    let tempImageAfter = DEFAULT_DATA.imageAfter;

    function onFacilityChange(facKey) {{
      if (VINMEC_FACILITIES[facKey]) {{
        currentReportData.facilityKey = facKey;
        currentReportData.hospitalName = VINMEC_FACILITIES[facKey].hospitalName;
        currentReportData.departmentName = VINMEC_FACILITIES[facKey].departmentName;
        currentReportData.hospitalAddress = VINMEC_FACILITIES[facKey].hospitalAddress;
        currentReportData.hospitalContact = VINMEC_FACILITIES[facKey].hospitalContact;
        renderReport(currentReportData);
      }}
    }}

    function onModalFacilityChange(facKey) {{
      if (VINMEC_FACILITIES[facKey]) {{
        document.getElementById("facilitySelector").value = facKey;
        onFacilityChange(facKey);
      }}
    }}

    function handleImageUpload(event, target) {{
      const file = event.target.files[0];
      if (file) {{
        const reader = new FileReader();
        reader.onload = function(e) {{
          const dataUrl = e.target.result;
          if (target === 'before') {{
            tempImageBefore = dataUrl;
            document.getElementById('modal_preview_before').src = dataUrl;
          }} else if (target === 'after') {{
            tempImageAfter = dataUrl;
            document.getElementById('modal_preview_after').src = dataUrl;
          }}
        }};
        reader.readAsDataURL(file);
      }}
    }}

    function renderReport(data) {{
      document.getElementById("field_hospitalName").innerText = data.hospitalName;
      document.getElementById("field_departmentName").innerText = data.departmentName;
      document.getElementById("field_hospitalAddress").innerText = data.hospitalAddress;
      document.getElementById("field_hospitalContact").innerText = data.hospitalContact;
      document.getElementById("field_reportTitle").innerText = data.reportTitle;
      document.getElementById("field_patientId").innerText = data.patientId;
      document.getElementById("field_patientName").innerText = data.patientName;
      document.getElementById("field_patientGender").innerText = data.patientGender;
      document.getElementById("field_patientDob").innerText = data.patientDob;
      document.getElementById("field_orderDate").innerText = data.orderDate;
      document.getElementById("field_visitType").innerText = data.visitType;
      document.getElementById("field_referringDoctor").innerText = data.referringDoctor;
      document.getElementById("field_serviceName").innerText = data.serviceName;
      document.getElementById("field_orderName").innerHTML = data.orderName;
      document.getElementById("field_completedDate").innerText = data.completedDate;
      document.getElementById("field_rpid").innerText = data.rpid;
      document.getElementById("field_clinicalDiagnosis").innerText = data.clinicalDiagnosis;
      document.getElementById("field_technique").innerText = data.technique;
      document.getElementById("field_ovary_r1").innerText = data.ovary_r1;
      document.getElementById("field_ovary_r2").innerText = data.ovary_r2;
      document.getElementById("field_ovary_r3").innerText = data.ovary_r3;
      document.getElementById("field_ovary_r4").innerText = data.ovary_r4;
      document.getElementById("field_ovary_l1").innerText = data.ovary_l1;
      
      const douglasElem = document.getElementById("field_douglas");
      if (douglasElem) {{
        douglasElem.innerText = data.douglas || "- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.";
      }}

      document.getElementById("field_conclusion_l1").innerText = data.conclusion_l1;
      document.getElementById("field_conclusion_l2").innerText = data.conclusion_l2;
      document.getElementById("field_doctorTitle").innerText = data.doctorTitle;
      document.getElementById("field_doctorName").innerText = data.doctorName;
      document.getElementById("field_footerApprovedBy").innerText = "Kết quả đã được duyệt bởi: " + data.doctorName + " — Hệ thống AI Decision Support v1.2";
      
      // Before - After Images
      if (data.imageBefore) {{
        document.getElementById("field_imageBefore").src = data.imageBefore;
      }}
      if (data.imageAfter) {{
        document.getElementById("field_imageAfter").src = data.imageAfter;
      }}
      if (data.imageBeforeCaption) {{
        document.getElementById("field_imageBeforeCaption").innerText = data.imageBeforeCaption;
      }}
      if (data.imageCaliperTag) {{
        document.getElementById("field_imageCaliperTag").innerText = data.imageCaliperTag;
      }}

      if (document.getElementById("facilitySelector")) {{
        document.getElementById("facilitySelector").value = data.facilityKey || "times_city";
      }}
    }}

    function openEditor() {{
      document.getElementById("modal_facilitySelector").value = currentReportData.facilityKey || "times_city";
      document.getElementById("input_patientId").value = currentReportData.patientId;
      document.getElementById("input_patientName").value = currentReportData.patientName;
      document.getElementById("input_patientGender").value = currentReportData.patientGender;
      document.getElementById("input_patientDob").value = currentReportData.patientDob;
      document.getElementById("input_orderDate").value = currentReportData.orderDate;
      document.getElementById("input_visitType").value = currentReportData.visitType;
      document.getElementById("input_referringDoctor").value = currentReportData.referringDoctor;
      document.getElementById("input_serviceName").value = currentReportData.serviceName;
      document.getElementById("input_orderName").value = currentReportData.orderName.replace("<br>", " ");
      document.getElementById("input_completedDate").value = currentReportData.completedDate;
      document.getElementById("input_rpid").value = currentReportData.rpid;
      document.getElementById("input_clinicalDiagnosis").value = currentReportData.clinicalDiagnosis;
      document.getElementById("input_technique").value = currentReportData.technique;
      document.getElementById("input_ovary_r1").value = currentReportData.ovary_r1;
      document.getElementById("input_ovary_r2").value = currentReportData.ovary_r2;
      document.getElementById("input_ovary_r3").value = currentReportData.ovary_r3;
      document.getElementById("input_ovary_r4").value = currentReportData.ovary_r4;
      document.getElementById("input_ovary_l1").value = currentReportData.ovary_l1;
      
      const inputDouglas = document.getElementById("input_douglas");
      if (inputDouglas) {{
        inputDouglas.value = currentReportData.douglas || "- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.";
      }}

      document.getElementById("input_conclusion_l1").value = currentReportData.conclusion_l1;
      document.getElementById("input_conclusion_l2").value = currentReportData.conclusion_l2;
      document.getElementById("input_doctorTitle").value = currentReportData.doctorTitle;
      document.getElementById("input_doctorName").value = currentReportData.doctorName;

      // Image inputs
      tempImageBefore = currentReportData.imageBefore;
      tempImageAfter = currentReportData.imageAfter;
      document.getElementById("modal_preview_before").src = currentReportData.imageBefore;
      document.getElementById("modal_preview_after").src = currentReportData.imageAfter;
      document.getElementById("input_imageBeforeCaption").value = currentReportData.imageBeforeCaption || "";
      document.getElementById("input_imageCaliperTag").value = currentReportData.imageCaliperTag || "";

      document.getElementById("editorModal").classList.add("active");
    }}

    function closeEditor() {{
      document.getElementById("editorModal").classList.remove("active");
    }}

    function applyEditorData() {{
      const selectedFac = document.getElementById("modal_facilitySelector").value;
      if (VINMEC_FACILITIES[selectedFac]) {{
        currentReportData.facilityKey = selectedFac;
        currentReportData.hospitalName = VINMEC_FACILITIES[selectedFac].hospitalName;
        currentReportData.departmentName = VINMEC_FACILITIES[selectedFac].departmentName;
        currentReportData.hospitalAddress = VINMEC_FACILITIES[selectedFac].hospitalAddress;
        currentReportData.hospitalContact = VINMEC_FACILITIES[selectedFac].hospitalContact;
      }}

      currentReportData.patientId = document.getElementById("input_patientId").value;
      currentReportData.patientName = document.getElementById("input_patientName").value;
      currentReportData.patientGender = document.getElementById("input_patientGender").value;
      currentReportData.patientDob = document.getElementById("input_patientDob").value;
      currentReportData.orderDate = document.getElementById("input_orderDate").value;
      currentReportData.visitType = document.getElementById("input_visitType").value;
      currentReportData.referringDoctor = document.getElementById("input_referringDoctor").value;
      currentReportData.serviceName = document.getElementById("input_serviceName").value;
      currentReportData.orderName = document.getElementById("input_orderName").value;
      currentReportData.completedDate = document.getElementById("input_completedDate").value;
      currentReportData.rpid = document.getElementById("input_rpid").value;
      currentReportData.clinicalDiagnosis = document.getElementById("input_clinicalDiagnosis").value;
      currentReportData.technique = document.getElementById("input_technique").value;
      currentReportData.ovary_r1 = document.getElementById("input_ovary_r1").value;
      currentReportData.ovary_r2 = document.getElementById("input_ovary_r2").value;
      currentReportData.ovary_r3 = document.getElementById("input_ovary_r3").value;
      currentReportData.ovary_r4 = document.getElementById("input_ovary_r4").value;
      currentReportData.ovary_l1 = document.getElementById("input_ovary_l1").value;
      
      const inputDouglas = document.getElementById("input_douglas");
      if (inputDouglas) {{
        currentReportData.douglas = inputDouglas.value;
      }}

      currentReportData.conclusion_l1 = document.getElementById("input_conclusion_l1").value;
      currentReportData.conclusion_l2 = document.getElementById("input_conclusion_l2").value;
      currentReportData.doctorTitle = document.getElementById("input_doctorTitle").value;
      currentReportData.doctorName = document.getElementById("input_doctorName").value;
      currentReportData.footerApprovedBy = "Kết quả đã được duyệt bởi: " + currentReportData.doctorName + " — Hệ thống AI Decision Support v1.2";

      // Save updated images
      currentReportData.imageBefore = tempImageBefore;
      currentReportData.imageAfter = tempImageAfter;
      currentReportData.imageBeforeCaption = document.getElementById("input_imageBeforeCaption").value;
      currentReportData.imageCaliperTag = document.getElementById("input_imageCaliperTag").value;

      renderReport(currentReportData);
      closeEditor();
    }}

    function resetDefaultData() {{
      currentReportData = JSON.parse(JSON.stringify(DEFAULT_DATA));
      tempImageBefore = DEFAULT_DATA.imageBefore;
      tempImageAfter = DEFAULT_DATA.imageAfter;
      renderReport(currentReportData);
    }}

    function openImageZoom(type) {{
      const imgSrc = type === 'before' ? currentReportData.imageBefore : currentReportData.imageAfter;
      const w = window.open('', '_blank');
      if (w) {{
        w.document.write(`
          <html>
            <head><title>Phóng to ảnh siêu âm ${{type.toUpperCase()}} - Vinmec Healthcare</title></head>
            <body style="background:#0f172a; margin:0; display:flex; align-items:center; justify-content:center; height:100vh;">
              <img src="${{imgSrc}}" style="max-width:95vw; max-height:95vh; object-fit:contain; border:2px solid #008ca8; border-radius:6px; box-shadow:0 10px 30px rgba(0,0,0,0.8);">
            </body>
          </html>
        `);
      }}
    }}

    window.addEventListener("DOMContentLoaded", () => {{
      renderReport(DEFAULT_DATA);
    }});
  </script>

</body>
</html>
'''

    target_path = r'templates/medical_report/vinmec_diagnosis_template.html'
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f'Successfully redesigned template in {target_path} (size: {len(html_content)} bytes)')

if __name__ == '__main__':
    main()
