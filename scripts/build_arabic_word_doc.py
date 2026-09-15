# -*- coding: utf-8 -*-
"""
Generate comprehensive Arabic Word Document (.docx) for Oracle EBS R12 MCP Studio.
Includes high-resolution screenshots, technical architecture, user guide, and security specifications.
"""

import os
import sys
import docx

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions for RTL & Styling
# ─────────────────────────────────────────────────────────────────────────────

def set_rtl(p):
    """Sets Right-to-Left property on a paragraph."""
    pPr = p._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    pPr.append(bidi)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

def set_run_font(run, font_name="Calibri", font_size_pt=11, bold=False, italic=False, color_rgb=(0,0,0)):
    """Sets Arabic & Latin fonts, size, boldness, and color on a run."""
    run.font.name = font_name
    run.font.size = Pt(font_size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)
    
    rPr = run._r.get_or_add_rPr()
    rtl = OxmlElement('w:rtl')
    rPr.append(rtl)
    
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:cs'), font_name)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rPr.append(rFonts)

def add_arabic_p(doc, text="", font_name="Calibri", font_size_pt=11, bold=False, italic=False, color_rgb=(31,41,55), align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=6):
    """Adds a paragraph styled with Arabic RTL."""
    p = doc.add_paragraph()
    set_rtl(p)
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.25
    if text:
        r = p.add_run(text)
        set_run_font(r, font_name, font_size_pt, bold, italic, color_rgb)
    return p

def add_arabic_heading(doc, text, level=1):
    """Adds a customized Arabic heading."""
    p = doc.add_paragraph()
    set_rtl(p)
    
    if level == 1:
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        set_run_font(r, font_name="Arial", font_size_pt=18, bold=True, color_rgb=(30, 58, 138)) # Navy
        # Add bottom border via XML
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         r'<w:bottom w:val="single" w:sz="12" w:space="4" w:color="1E3A8A"/>'
                         r'</w:pBdr>')
        pPr.append(pBdr)
    elif level == 2:
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        set_run_font(r, font_name="Arial", font_size_pt=14, bold=True, color_rgb=(13, 148, 136)) # Teal
    elif level == 3:
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        set_run_font(r, font_name="Calibri", font_size_pt=12, bold=True, color_rgb=(37, 99, 235)) # Royal Blue
    return p

def add_callout(doc, text, title="ملاحظة هامة", box_type="info"):
    """Adds a stylish callout box for warnings/tips/notes."""
    table = doc.add_table(rows=1, cols=1)
    set_table_rtl(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    
    # Border & Background
    if box_type == "warning":
        bg_color = "FEF3C7" # light amber
        border_color = "D97706" # amber
        icon = "⚠️ "
        title_color = (180, 83, 9)
    elif box_type == "danger":
        bg_color = "FEE2E2" # light red
        border_color = "DC2626" # red
        icon = "🛑 "
        title_color = (185, 28, 28)
    else:
        bg_color = "F0FDF4" # light emerald
        border_color = "059669" # green
        icon = "💡 "
        title_color = (4, 120, 87)

    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                          f'<w:top w:val="none"/>'
                          f'<w:left w:val="none"/>'
                          f'<w:bottom w:val="none"/>'
                          f'<w:right w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
                          f'</w:tcBorders>')
    tcPr.append(shd)
    tcPr.append(tcBorders)
    
    p = cell.paragraphs[0]
    set_rtl(p)
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(f"{icon}{title}")
    set_run_font(r_title, "Arial", 11, bold=True, color_rgb=title_color)
    
    p2 = cell.add_paragraph()
    set_rtl(p2)
    p2.paragraph_format.space_after = Pt(4)
    r_body = p2.add_run(text)
    set_run_font(r_body, "Calibri", 10.5, color_rgb=(31, 41, 55))
    
    # Empty paragraph after table for spacing
    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(6)

def set_table_rtl(table):
    """Configures table for Right-to-Left layout in Microsoft Word."""
    tblPr = table._tbl.tblPr
    bidiVisual = OxmlElement('w:bidiVisual')
    tblPr.append(bidiVisual)

def add_arabic_image(doc, img_path, caption):
    """Adds an image with center alignment and an Arabic caption."""
    if not os.path.exists(img_path):
        print(f"Warning: Image not found: {img_path}")
        return
    
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(4)
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=Inches(6.4))
    
    p_cap = doc.add_paragraph()
    set_rtl(p_cap)
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_after = Pt(12)
    r_cap = p_cap.add_run(f"شكل توضيحي: {caption}")
    set_run_font(r_cap, font_name="Calibri", font_size_pt=10, italic=True, color_rgb=(75, 85, 99))

def style_table(table, header_bg="1E3A8A", alt_bg="F9FAFB"):
    """Applies clean enterprise borders, header backgrounds, and alternating row colors."""
    set_table_rtl(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Borders
    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="D1D5DB"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="D1D5DB"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E5E7EB"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)

    for i, row in enumerate(table.rows):
        # Prevent row split across pages
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))
        
        is_header = (i == 0)
        if is_header:
            trPr.append(OxmlElement('w:tblHeader'))

        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            tcPr = cell._tc.get_or_add_tcPr()
            
            # Margins
            tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}>'
                              f'<w:top w:w="120" w:type="dxa"/>'
                              f'<w:bottom w:w="120" w:type="dxa"/>'
                              f'<w:left w:w="160" w:type="dxa"/>'
                              f'<w:right w:w="160" w:type="dxa"/>'
                              f'</w:tcMar>')
            tcPr.append(tcMar)
            
            # Background shading
            if is_header:
                shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{header_bg}"/>')
            elif i % 2 == 1:
                shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{alt_bg}"/>')
            else:
                shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="FFFFFF"/>')
            tcPr.append(shd)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DOCUMENT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_word_document():
    doc = Document()

    # Configure Margins (Normal 1 inch)
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.9)
        s.bottom_margin = Inches(0.9)
        s.left_margin = Inches(0.85)
        s.right_margin = Inches(0.85)

    img_dir = os.path.abspath("images_doc")

    # ═════════════════════════════════════════════════════════════════════════
    # 1. صفحة الغلاف (Cover Page)
    # ═════════════════════════════════════════════════════════════════════════
    
    # Top spacing
    p_cov_space = doc.add_paragraph()
    p_cov_space.paragraph_format.space_before = Pt(40)

    # Project Title
    p_title = doc.add_paragraph()
    set_rtl(p_title)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p_title.add_run("منصة واستوديو التطوير الذكي لـ Oracle EBS R12\n")
    set_run_font(r1, "Arial", 26, bold=True, color_rgb=(30, 58, 138))
    
    r2 = p_title.add_run("Oracle E-Business Suite R12 - MCP Studio & Live Deployment Gateway")
    set_run_font(r2, "Arial", 14, bold=False, color_rgb=(100, 116, 139))
    p_title.paragraph_format.space_after = Pt(20)

    # Subtitle / Abstract Box
    add_callout(
        doc,
        "توثيق شامل ومعماري متقدم لمنظومة الربط الذكي بين نماذج الذكاء الاصطناعي (Claude, Antigravity, Cursor) "
        "وبيئة وتطبيقات أوراكل للأعمال (Oracle EBS R12 APPS Schema). يشمل الدليل شرح المعمارية التقنية، محرك النشر التلقائي المباشر، "
        "معايير الأمان المؤسسي الصارم، والواجهة الرسومية التفاعلية مع تدعيم كل وحدة بالصور التوضيحية للشاشات الحية.",
        title="دليل التوثيق التقني والتشغيلي الشامل",
        box_type="info"
    )

    p_meta = doc.add_paragraph()
    set_rtl(p_meta)
    p_meta.paragraph_format.space_before = Pt(40)
    p_meta.paragraph_format.space_after = Pt(20)
    p_meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    meta_items = [
        ("اسم المشروع:", "Oracle EBS R12 MCP Development Studio"),
        ("الجهة المطورة:", "راية لتكنولوجيا المعلومات (Raya IT) - قسم الحلول المؤسسية والذكاء الاصطناعي"),
        ("إصدار المنظومة:", "الإصدار 2.0 (Enterprise Release)"),
        ("تاريخ الوثيقة:", "سبتمبر 2026"),
        ("البيئة المستهدفة:", "Oracle E-Business Suite Release 12.2 / 12.1 (APPS Schema)"),
        ("بروتوكولات الربط:", "Model Context Protocol (MCP) + SSH Tunnel (plink) + SQL*Plus Stdin")
    ]

    for label, val in meta_items:
        p_row = doc.add_paragraph()
        set_rtl(p_row)
        p_row.paragraph_format.space_after = Pt(3)
        r_lbl = p_row.add_run(f"• {label} ")
        set_run_font(r_lbl, "Arial", 11, bold=True, color_rgb=(30, 58, 138))
        r_val = p_row.add_run(val)
        set_run_font(r_val, "Calibri", 11, color_rgb=(55, 65, 81))

    doc.add_page_break()

    # ═════════════════════════════════════════════════════════════════════════
    # 2. جدول المحتويات والملخص التنفيذي
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "فهرس محتويات الدليل التقني", level=1)
    
    toc_items = [
        "1. الملخص التنفيذي وأهداف المشروع (Executive Summary)",
        "2. المشكلات والتحديات الهندسية التي يعالجها النظام",
        "3. المعمارية التقنية وأمن الجلسات (Architecture & Security Guardrails)",
        "4. جولة مصورة في واجهة الاستوديو التفاعلي (MCP Studio Visual Walkthrough):",
        "   - 4.1 شاشة التحكم العامة وإدارة بيئات العمل (Environments Selector)",
        "   - 4.2 استوديو البرامج المتزامنة (Concurrent Program Studio)",
        "   - 4.3 استوديو تقارير أوراكل (BI Publisher & XML Publisher Studio)",
        "   - 4.4 استوديو مسارات سير العمل (Oracle Workflow Engine)",
        "   - 4.5 استوديو إدارة التنبيهات والأحداث (Oracle Alert Manager)",
        "   - 4.6 استوديو صفحات إطار عمل أوراكل (OAF Studio & MDS Repository)",
        "   - 4.7 استوديو استعلامات SQL و PL/SQL المباشرة والمحمية",
        "   - 4.8 منظومة حماية بيئة الإنتاج الصارمة (Production Safety Guard)",
        "5. بوابة النشر والتحقق التلقائي في قاعدة البيانات (Live Gateway & Verification)",
        "6. كتالوج أدوات الذكاء الاصطناعي (MCP Tools Reference)",
        "7. دليل التثبيت والتشغيل السريع (Installation & Deployment Guide)"
    ]

    for item in toc_items:
        p_t = doc.add_paragraph()
        set_rtl(p_t)
        p_t.paragraph_format.space_after = Pt(2)
        r_t = p_t.add_run(item)
        bold_flag = not item.startswith("   -")
        color = (30, 58, 138) if bold_flag else (75, 85, 99)
        set_run_font(r_t, "Calibri", 10.5, bold=bold_flag, color_rgb=color)

    # ═════════════════════════════════════════════════════════════════════════
    # 3. الملخص التنفيذي والأهداف
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "1. الملخص التنفيذي وأهداف المشروع (Executive Summary)", level=1)

    add_arabic_p(
        doc,
        "تعتبر بيئة أوراكل للأعمال (Oracle E-Business Suite R12) إحدى أضخم وأعقد منصات إدارة الموارد المؤسسية (ERP) في العالم، "
        "حيث تعتمد عليها كبرى المؤسسات الحكومية والخاصة لإدارة وظائف الموارد البشرية (HRMS)، والمالية (GL/AP/AR)، "
        "والمشتريات (PO)، وسلسلة الإمداد. ورغم قوتها الشديدة، إلا أن دورة تطوير التقارير والكائنات (Extensions/Customizations) "
        "فيها تتسم بالتعقيد العالي، وتتطلب خطوات يدوية طويلة لتسجيل البرامج المتزامنة، ورفع قوالب RTF، وربط مجموعات الصلاحيات (Request Groups)."
    )

    add_arabic_p(
        doc,
        "مشروع Oracle EBS R12 MCP Studio يمثل قفزة نوعية في دمج الذكاء الاصطناعي التوليدي التفاعلي (Generative AI) "
        "مع بيئة أوراكل؛ حيث يوفر المنصة الموحدة الأولى التي تتيح لمطوري ومسؤولي أوراكل (EBS Developers & DBAs) "
        "ونماذج الذكاء الاصطناعي (مثل Claude و Antigravity IDE) التواصل الآمن، وتوليد الشيفرات البرمجية المتوافقة بنسبة 100% "
        "مع معايير أوراكل المعتمدة، ثم نشرها والتحقق منها مباشرة في قاعدة البيانات بضغطة زر واحدة."
    )

    add_callout(
        doc,
        "المنصة تدمج بين خادم بروتوكول الذكاء الاصطناعي (MCP Server) وبوابة نشر حي (Live Deployment Gateway) "
        "وواجهة استوديو متقدمة (Web Studio UI) تضمن عدم المساس بأمن قاعدة البيانات أو انتهاك صلاحيات المؤسسة.",
        title="القيمة المضافة للمنظومة",
        box_type="info"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # 4. المعمارية التقنية وأمن الجلسات
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "2. المعمارية التقنية وأمن الجلسات (Architecture & Security Guardrails)", level=1)

    add_arabic_p(
        doc,
        "تم تصميم النظام وفق أعلى معايير الأمان المؤسسي الصارم لمنع أي محاولات للاختراق، أو حقن الأوامر (Command Injection)، "
        "أو تجاوز الصلاحيات الممنوحة للمستخدمين. يوضح المخطط التالي دورة معالجة الطلبات بدءاً من مساعد الذكاء الاصطناعي وحتى وصولها للـ EBS:"
    )

    # Table of Architecture Layers
    tbl_arch = doc.add_table(rows=5, cols=3)
    style_table(tbl_arch, header_bg="1E3A8A")

    headers = ["الطبقة المعمارية", "المكون والتقنية المستخدمة", "الدور والوظيفة الأساسية"]
    for col_idx, text in enumerate(headers):
        cell = tbl_arch.cell(0, col_idx)
        p = cell.paragraphs[0]
        set_rtl(p)
        r = p.add_run(text)
        set_run_font(r, "Arial", 10.5, bold=True, color_rgb=(255, 255, 255))

    arch_data = [
        ("طبقة مساعد الذكاء الاصطناعي\n(AI Assistant Layer)", "Claude / Antigravity / Cursor\n(Model Context Protocol)", "فهم المتطلبات باللغة الطبيعية واستدعاء أدوات EBS المخصصة بأمان."),
        ("طبقة خادم البروتوكول\n(MCP Server Layer)", "Python FastMCP Engine\n(JSON-RPC 2.0 / stdio)", "معالجة المدخلات، تطبيق فلاتر الأمان والتحقق من قائمة البرامج المسموحة (Allowlist)."),
        ("بوابة النشر الحي المباشر\n(Live Gateway Layer)", "EBS Live Deployment Engine\n(Python HTTP Server + SFTP)", "إدارة نفق الاتصال الآمن مع خادم أوراكل وتنفيذ السكربتات وتوفير واجهة الويب."),
        ("طبقة قاعدة بيانات أوراكل\n(Oracle EBS R12 Layer)", "Oracle Database (APPS Schema)\nFND APIs (Concurrent / Security)", "تفعيل سياق الجلسة الآمن FND_GLOBAL.APPS_INITIALIZE وتنفيذ برامج أوراكل الرسمية.")
    ]

    for row_idx, data in enumerate(arch_data, start=1):
        for col_idx, text in enumerate(data):
            cell = tbl_arch.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            set_rtl(p)
            r = p.add_run(text)
            set_run_font(r, "Calibri", 10, bold=(col_idx==0), color_rgb=(31, 41, 55))

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(8)

    add_arabic_heading(doc, "ركائز الأمان الصارم في المنظومة (Security Guardrails)", level=2)

    security_points = [
        ("منع تنفيذ أوامر SQL العشوائية (No Arbitrary SQL Execution):", "لا يوجد أي أداة تسمح بتنفيذ أوامر DDL أو DML تخريبية مثل DROP أو TRUNCATE أو DELETE عشوائية في بيئة APPS."),
        ("فلترة المعاملات وحظر حقن الأوامر (Shell & SQL Injection Blocking):", "يتم فحص وتطهير كافة المعاملات وحظر الرموز الخاصة مثل (`, ;, &, |, $, >, <) تلقائياً."),
        ("قائمة البرامج المسموحة الحصرية (Strict Allowlist):", "يتم تقييد استدعاء وتشغيل البرامج المتزامنة بقائمة محددة مسبقاً في متغيرات البيئة (ALLOWED_CONCURRENT_PROGRAMS)."),
        ("تهيئة سياق الجلسة الآمن (FND_GLOBAL.APPS_INITIALIZE):", "ربط كافة الطلبات بهوية مستخدم حقيقية (SYSADMIN) ومسؤولية معتمدة (Global HRMS Manager) لضمان تطبيق سياسات MOAC و HR Security Profiles."),
        ("إخفاء البيانات السرية وكلمات المرور (Masking Credentials):", "تشفير وحجب أي كلمات مرور أو مفاتيح سرية في سجلات النظام وسجلات الاستجابة.")
    ]

    for title, desc in security_points:
        p_sec = doc.add_paragraph()
        set_rtl(p_sec)
        p_sec.paragraph_format.space_after = Pt(4)
        r_t = p_sec.add_run(f"🔒 {title} ")
        set_run_font(r_t, "Arial", 10.5, bold=True, color_rgb=(30, 58, 138))
        r_d = p_sec.add_run(desc)
        set_run_font(r_d, "Calibri", 10.5, color_rgb=(55, 65, 81))

    doc.add_page_break()

    # ═════════════════════════════════════════════════════════════════════════
    # 5. جولة مصورة في واجهة الاستوديو التفاعلي
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "3. جولة مصورة في واجهة الاستوديو التفاعلي (Visual Walkthrough)", level=1)

    add_arabic_p(
        doc,
        "توفر واجهة الويب التفاعلية (Web Studio UI) منصة متكاملة عالية الاحترافية لمطوري أوراكل، "
        "مقسمة بذكاء إلى لوحة إعداد المعاملات على اليسار (Configuration Pane) وشاشة استعراض وتحميل الأكواد على اليمين (Generated Artifacts)، "
        "مع إمكانية النشر المباشر بضغطة زر. نستعرض فيما يلي كافة الوحدات مدعومة بالصور الحية الملتقطة من بيئة التشغيل:"
    )

    # 3.1 شاشة التحكم العامة وإدارة بيئات العمل
    add_arabic_heading(doc, "3.1 شاشة التحكم العامة ومحدد بيئات العمل (Environments Selector)", level=2)
    add_arabic_p(
        doc,
        "تتيح شاشة التحكم العلوية مراقبة حالة الاتصال مع خادم أوراكل بصورة فورية، وتحديد بيئة العمل المستهدفة (DEV, TEST, UAT, PROD). "
        "يتم عرض اسم الخادم المستهدف (HRVIS - 10.100.100.104) ونقطة النهاية النشطة، مع أزرار النشر السريع والتحقق المباشر من قاعدة البيانات."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "01_dashboard_overview.png"),
        "واجهة لوحة التحكم الرئيسية - محدد البيئات وشريط الأدوات العلوي"
    )

    # 3.2 استوديو البرامج المتزامنة
    add_arabic_heading(doc, "3.2 استوديو البرامج المتزامنة (Concurrent Program Studio)", level=2)
    add_arabic_p(
        doc,
        "تعتبر وحدة البرامج المتزامنة حجر الزاوية في تطوير إضافات EBS R12. تمكّن الوحدة المطور من تعريف البرنامج التنفيذي (Executable)، "
        "واختيار طريقة التنفيذ (PL/SQL Stored Procedure, SQL*Plus, Oracle Reports, Host)، وضبط المعاملات في جدول ديناميكي تفاعلي "
        "يحدد الترتيب، نوع القيمة (Value Set)، وحالة الإلزامية. يتم توليد حزمة متكاملة من كود FND_PROGRAM والسكربت الحامي ومجموعة الصلاحيات (Request Group)."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "02_concurrent_module.png"),
        "استوديو البرامج المتزامنة - جدول المعاملات التفاعلي والشيفرة التلقائية المولدة"
    )

    # 3.3 استوديو تقارير أوراكل
    add_arabic_heading(doc, "3.3 استوديو تقارير أوراكل (BI Publisher & XML Publisher Studio)", level=2)
    add_arabic_p(
        doc,
        "توفر هذه الوحدة دورة حياة كاملة لبناء تقارير أوراكل المعتمدة على محرك XML Publisher / BI Publisher؛ حيث يتم إدخال استعلام SQL "
        "ليقوم النظام بتحليله آلياً، واستخراج الحقول والأعمدة، ثم توليد ملف نموذج البيانات (Data Template XML)، "
        "وملف العينة التجريبية (Sample Data XML)، وقالب التنسيق النهائي (RTF Template)، "
        "بالإضافة إلى أوامر أداة التحميل المعتمدة من أوراكل (XDOLoader CLI) لرفع القالب إلى خادم التطبيقات بنجاح."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "03_report_generator.png"),
        "استوديو تقارير BI Publisher - توليد قوالب Data Template و RTF و XDOLoader"
    )

    doc.add_page_break()

    # 3.4 استوديو مسارات سير العمل
    add_arabic_heading(doc, "3.4 استوديو مسارات سير العمل (Oracle Workflow Engine)", level=2)
    add_arabic_p(
        doc,
        "تسهل وحدة Workflow أتمتة الإجراءات والاعتمادات الإدارية؛ حيث تتيح تعريف نوع العنصر (Item Type)، "
        "ورسم خطوات المسار (Process Flow Activities)، وإعداد رسائل التنبيهات والإشعارات (Notifications). "
        "يقوم النظام بتوليد سكربت التثبيت المتوافق مع أداة التحميل الرسمية WF_LOAD، وحزمة PL/SQL البرمجية المعالجة لأحداث المسار، "
        "وسكربت اختبار بدء المسار (Workflow Starter Test Script)."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "04_workflow_manager.png"),
        "استوديو مسارات سير العمل - توليد تعريفات WF_LOAD وحزم معالجة الإشعارات"
    )

    # 3.5 استوديو إدارة التنبيهات والأحداث
    add_arabic_heading(doc, "3.5 استوديو إدارة التنبيهات والأحداث (Oracle Alert Manager)", level=2)
    add_arabic_p(
        doc,
        "تتيح وحدة Alert Manager مراقبة حركة البيانات داخل قاعدة بيانات EBS وإنشاء تنبيهات فورية (Event Alerts) "
        "عند حدوث تعديل في جداول معينة، أو تنبيهات دورية (Periodic Alerts) مجدولة زمنياً. "
        "يقوم النظام بإنشاء سكربت تسجيل التنبيه في جداول ALR_ALERTS، وتوليد نموذج نص الرسالة، وتحديد قوائم التوزيع، "
        "مع إمكانية تفعيل الإجراءات التلقائية (Actions) مثل إرسال بريد إلكتروني أو تشغيل برنامج متزامن."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "05_alert_manager.png"),
        "استوديو التنبيهات - صياغة استعلامات الفحص وقوائم الإشعار التلقائية"
    )

    # 3.6 استوديو صفحات إطار عمل أوراكل OAF
    add_arabic_heading(doc, "3.6 استوديو صفحات إطار عمل أوراكل (OAF Studio & MDS Repository)", level=2)
    add_arabic_p(
        doc,
        "تختص هذه الوحدة بتطوير صفحات الويب القائمة على تقنية Oracle Application Framework (OAF). "
        "تسمح المنظومة ببناء هيكل الصفحة بتنسيق XML، وتوليد فئات التحكم في الجافا (Java Controller - OAControllerImpl)، "
        "وتجهيز أوامر أداة الاستيراد إلى مستودع البيانات التعريفي (XMLImporter into MDS)، "
        "بالإضافة إلى إرشادات إعادة تشغيل خدمات الويب (OA Core Bounce Commands) لتطبيق التعديلات."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "06_oaf_studio.png"),
        "استوديو صفحات OAF - توليد كود XML ومتحكمات Java وأوامر استيراد MDS"
    )

    doc.add_page_break()

    # 3.7 استوديو استعلامات SQL و PL/SQL
    add_arabic_heading(doc, "3.7 استوديو استعلامات SQL و PL/SQL المباشرة والمحمية", level=2)
    add_arabic_p(
        doc,
        "توفر وحدة SQL Studio محرر استعلامات متخصص لمطوري أوراكل للاتصال المباشر مع مخطط APPS. "
        "تتميز الوحدة بنظام فحص وتحليل فوري لضمان السلامة، مع إمكانية عرض النتائج في شبكة جداول منسقة، "
        "وتوليد أوامر التراجع (Rollback Scripts) بصورة آلية لكل جملة تعديل، بما يضمن عدم إحداث أي خلل في بيانات النظام."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "07_sql_plsql_studio.png"),
        "استوديو استعلامات SQL - تنفيذ آمن في مخطط APPS مع سجل تدقيق وسكربتات تراجع"
    )

    # 3.8 منظومة حماية بيئة الإنتاج الصارمة
    add_arabic_heading(doc, "3.8 منظومة حماية بيئة الإنتاج الصارمة (Production Safety Guard)", level=2)
    add_arabic_p(
        doc,
        "تفرض المنصة معايير أمان إضافية عند التبديل إلى بيئة الإنتاج الحية (PROD)؛ حيث يظهر شريط تحذيري باللون الأحمر الفاقع، "
        "ويتم قفل أزرار التنفيذ المباشر التلقائي، وإلزام المطور بمراجعة سكربتات النشر والتراجع، وتطبيق معايير إدارة التغيير المؤسسية (MD120)."
    )
    add_arabic_image(
        doc,
        os.path.join(img_dir, "08_production_safety.png"),
        "شاشة حماية بيئة الإنتاج (PROD) - تفعيل القفل الأمني والشريط التحذيري الإلزامي"
    )

    doc.add_page_break()

    # ═════════════════════════════════════════════════════════════════════════
    # 6. بوابة النشر والتحقق التلقائي في قاعدة البيانات
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "4. بوابة النشر والتحقق التلقائي (Live Deployment & Verification)", level=1)

    add_arabic_p(
        doc,
        "أحد أهم الابتكارات في هذا المشروع هو بوابة النشر الحي (Live Deployment Gateway). "
        "في الطرق التقليدية، يحتاج المطور لفتح برنامج WinSCP أو FileZilla لرفع الملفات، ثم فتح جلسة PuTTY لتشغيل سكربتات SQL*Plus وأوامر XDOLoader. "
        "تقوم بوابتنا الذكية بأتمتة هذه السلسلة المعقدة بالكامل عبر واجهة برمجة تطبيقات خفيفة وفائقة السرعة:"
    )

    # Table of Deployment Routing
    tbl_dep = doc.add_table(rows=8, cols=3)
    style_table(tbl_dep, header_bg="0D9488")

    dep_headers = ["نوع الكائن (Object Type)", "طريقة ومسار النشر التلقائي", "إجراء التحقق في قاعدة البيانات (DB Verification)"]
    for col_idx, text in enumerate(dep_headers):
        cell = tbl_dep.cell(0, col_idx)
        p = cell.paragraphs[0]
        set_rtl(p)
        r = p.add_run(text)
        set_run_font(r, "Arial", 10.5, bold=True, color_rgb=(255, 255, 255))

    dep_data = [
        ("Concurrent Program", "تنفيذ باقة FND_PROGRAM عبر APPS SQL*Plus", "التحقق من وجود البرنامج في FND_CONCURRENT_PROGRAMS"),
        ("Workflow", "تحميل الملف عبر WF_LOAD.UPLOAD_ITEM_TYPE", "التحقق من حالة نوع العنصر في WF_ITEM_TYPES_VL"),
        ("Oracle Alert", "تسجيل التنبيه وإجراءاته في جداول ALR_ALERTS", "التحقق من وجود وتفعيل التنبيه في ALR_ALERTS"),
        ("OAF Component", "استيراد XMLImporter للمسار المحدد في MDS", "التحقق من تسجيل الوثيقة في مستودع JDR_PATHS"),
        ("Oracle Report (RDF)", "رفع الملف الثنائي عبر SFTP إلى مسار $AU_TOP/reports/US", "التحقق من وجود الملف التنفيذي والبرنامج في FND"),
        ("XML Publisher (RTF)", "رفع القالب وتسجيله كـ BLOB في XDO_LOBS", "التحقق من وجود القالب في XDO_TEMPLATES_B"),
        ("SQL / PL-SQL Package", "تنفيذ الشيفرة عبر SQL*Plus Stdin المباشر والمحمي", "التحقق من صلاحية الكائن (STATUS = 'VALID') في ALL_OBJECTS")
    ]

    for row_idx, data in enumerate(dep_data, start=1):
        for col_idx, text in enumerate(data):
            cell = tbl_dep.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            set_rtl(p)
            r = p.add_run(text)
            set_run_font(r, "Calibri", 10, bold=(col_idx==0), color_rgb=(31, 41, 55))

    add_callout(
        doc,
        "تقنية SQL*Plus Stdin المطبقة في النظام تمنع تشويه المتغيرات وعلامات التنصيص (Quotation Mangle)، "
        "وتضمن تنفيذ السكربتات الضخمة المعقدة دون التأثر بمحددات أسطر الأوامر في أنظمة التشغيل.",
        title="ميزة هندسية فريدة",
        box_type="tip"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # 7. كتالوج أدوات الذكاء الاصطناعي
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "5. كتالوج أدوات الذكاء الاصطناعي (MCP Tools Reference)", level=1)

    add_arabic_p(
        doc,
        "يوفر خادم MCP مصفوفة من الأدوات المعيارية التي تستطيع نماذج الذكاء الاصطناعي (مثل مساعد Claude) "
        "استدعاءها مباشرة لتقديم الدعم الفني للمطورين والمديرين في المؤسسة:"
    )

    # MCP tools table
    tbl_tools = doc.add_table(rows=6, cols=3)
    style_table(tbl_tools, header_bg="1E3A8A")

    tools_headers = ["اسم الأداة (Tool Name)", "المدخلات المطلوبة", "الوظيفة والمخرجات"]
    for col_idx, text in enumerate(tools_headers):
        cell = tbl_tools.cell(0, col_idx)
        p = cell.paragraphs[0]
        set_rtl(p)
        r = p.add_run(text)
        set_run_font(r, "Arial", 10.5, bold=True, color_rgb=(255, 255, 255))

    tools_data = [
        ("list_allowed_concurrent_programs", "لا توجد مدخلات مطلوبة", "استرجاع قائمة البرامج المتزامنة المصرح للمساعد الذكي بتشغيلها مع وصف كل برنامج ومسؤوليته."),
        ("submit_concurrent_request", "اسم البرنامج، المعاملات، اسم التطبيق", "تفعيل سياق APPS_INITIALIZE وتقديم الطلب المتزامن وإرجاع رقم الطلب الفريد (Request ID)."),
        ("get_concurrent_request_status", "رقم الطلب (request_id)", "مراقبة المرحلة الحالية (Phase) وحالة التشغيل (Status) والوقت المنقضي للطلب في الـ Concurrent Manager."),
        ("wait_for_concurrent_request", "رقم الطلب، مهلة الانتظار (timeout)", "الانتظار الذكي حتى اكتمال الطلب وإرجاع النتيجة النهائية (Normal / Error / Warning)."),
        ("get_concurrent_request_log", "رقم الطلب (request_id)", "جلب وتطهير سجل التشغيل (Log File) وعرضه للمستخدم مع حجب أي بيانات حساسة أو كلمات مرور.")
    ]

    for row_idx, data in enumerate(tools_data, start=1):
        for col_idx, text in enumerate(data):
            cell = tbl_tools.cell(row_idx, col_idx)
            p = cell.paragraphs[0]
            set_rtl(p)
            r = p.add_run(text)
            set_run_font(r, "Calibri", 10, bold=(col_idx==0), color_rgb=(31, 41, 55))

    doc.add_page_break()

    # ═════════════════════════════════════════════════════════════════════════
    # 8. دليل التثبيت والتشغيل السريع
    # ═════════════════════════════════════════════════════════════════════════
    add_arabic_heading(doc, "6. دليل التثبيت والتشغيل السريع (Installation & Quick Start)", level=1)

    add_arabic_p(
        doc,
        "يمكن تشغيل المنظومة بسهولة على بيئات Windows أو Linux باتباع الخطوات التالية:"
    )

    steps = [
        ("الخطوة الأولى: تثبيت الحزم البرمجية", "التأكد من توفر بيئة Python 3.10+ وتشغيل الأمر: pip install -r requirements.txt"),
        ("الخطوة الثانية: ضبط إعدادات الاتصال", "نسخ ملف الإعدادات .env.example إلى .env وتحديد معطيات اتصال قاعدة بيانات أوراكل وسياق الجلسة (ORACLE_HOST, EBS_USERNAME, ALLOWED_CONCURRENT_PROGRAMS)."),
        ("الخطوة الثالثة: تشغيل بوابة الاستوديو", "لتشغيل بوابة النشر وخادم الويب التفاعلي على المنفذ 8855: python ui/server_launcher.py"),
        ("الخطوة الرابعة: تشغيل خادم بروتوكول الذكاء الاصطناعي", "لتشغيل خادم MCP وربطه بتطبيقات الذكاء الاصطناعي: python -m src.server"),
        ("الخطوة الخامسة: الربط مع Claude Desktop", "إضافة إعدادات الخادم في ملف claude_desktop_config.json لتتمكن نماذج Claude من تنفيذ المهام مباشرة.")
    ]

    for title, desc in steps:
        p_step = doc.add_paragraph()
        set_rtl(p_step)
        p_step.paragraph_format.space_after = Pt(4)
        r_num = p_step.add_run(f"📌 {title}: ")
        set_run_font(r_num, "Arial", 11, bold=True, color_rgb=(30, 58, 138))
        r_desc = p_step.add_run(desc)
        set_run_font(r_desc, "Calibri", 10.5, color_rgb=(55, 65, 81))

    p_spacer2 = doc.add_paragraph()
    p_spacer2.paragraph_format.space_after = Pt(12)

    add_arabic_heading(doc, "الخاتمة والتوصيات المستقبلية", level=2)
    add_arabic_p(
        doc,
        "يمثل مشروع Oracle EBS R12 MCP Studio نموذجاً رائداً في تسخير أحدث تقنيات الذكاء الاصطناعي التوليدي "
        "لتحديث بيئات المؤسسات الضخمة دون التضحية بمعايير الأمان والاستقرار. "
        "يوفر النظام على فرق التطوير والدعم مئات الساعات المهدرة في الإجراءات اليدوية الروتينية، "
        "ويقلل بنسبة تزيد عن 90% من الأخطاء البشرية الشائعة في تعريف وتسجيل الكائنات في أوراكل."
    )

    # Save Document
    doc_path = os.path.abspath("دليل_مشروع_Oracle_EBS_R12_MCP_Studio.docx")
    doc.save(doc_path)
    print(f"[SUCCESS] Document successfully generated and saved at:\n{doc_path}")

    # Also save an english filename copy for easy cross-referencing
    alt_path = os.path.abspath("Oracle_EBS_R12_MCP_Studio_Documentation_AR.docx")
    doc.save(alt_path)
    print(f"[SUCCESS] Secondary copy saved at:\n{alt_path}")

if __name__ == "__main__":
    build_word_document()
