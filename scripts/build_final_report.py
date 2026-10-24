"""
Builds SplitSmart Project Report (.docx) perfectly matching the reference PDF:
- Header & Footer on all pages
- 1. Project Overview & Problem Statement (2 natural paragraphs, no feature bullet lists)
- 2. Technology Stack & Architectural Design (Table with full vertical and horizontal grid lines)
- 3. Uploaded Project Files & Roles (Table with full vertical and horizontal grid lines)
- 4. System Flowchart & Operational Pipeline (Reference-style two-phase flowchart image + brief summary)
- 5. How to Run the Program (Step-by-Step with shaded code boxes, clarifying venv & environment)
- 6. Core Mathematical Logic & Algorithms (In Brief: Debt Minimizer, Family Rollup, Itemized Split, Kitty Pool)
- 7. Testing & Verification (Brief breakdown of unit tests, edge cases, and terminal OK pass)
- 8. Visual Results & Application Screenshots (5 neat framed screenshot placeholder boxes)
- 9. Conclusion
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    """Sets background shading of a table cell."""
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

def set_cell_margins(cell, top=70, bottom=70, left=100, right=100):
    """Sets internal padding for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for margin_name, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{margin_name}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="6"):
    """Applies clean full grid borders with both horizontal and vertical lines."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def add_code_box(doc, code_text):
    """Creates a clean light gray terminal code block box matching the reference style."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
    
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
        f'<w:left w:val="single" w:sz="18" w:space="0" w:color="3B82F6"/>'
        f'<w:right w:val="single" w:sz="6" w:space="0" w:color="E2E8F0"/>'
        f'</w:tcBorders>'
    )
    cell._tc.get_or_add_tcPr().append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(4)

def add_figure_text(doc, figure_num, caption, *args):
    """Outputs clean figure caption text with spacing for pasting screenshots (no box), matching reference PDF."""
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(12)
    p_img.paragraph_format.space_after = Pt(2)
    
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_run = cap_p.add_run(f"Figure {figure_num}: {caption}")
    cap_run.font.name = "Calibri"
    cap_run.font.size = Pt(9.5)
    cap_run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    cap_run.italic = True
    cap_p.paragraph_format.space_before = Pt(2)
    cap_p.paragraph_format.space_after = Pt(16)

add_screenshot_box = add_figure_text

def generate_report():
    doc = docx.Document()
    
    # Page Margins (1 inch)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        
        # Header (Top Right)
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("Project Assignment Report | SplitSmart")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
        # Footer (Center)
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = fp.add_run("SplitSmart • AI-Assisted Group Expense Engine | Report")
        frun.font.name = "Calibri"
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)

    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(5)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    flowchart_img = os.path.join(base_dir, "scripts", "flowchart.png")

    # Headings
    def add_h1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
        r = h.add_run(text)
        r.bold = True
        r.font.name = 'Calibri'
        r.font.size = Pt(14)
        r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(3)
        r = h.add_run(text)
        r.bold = True
        r.font.name = 'Calibri'
        r.font.size = Pt(11.5)
        r.font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8)
        return h

    # ==========================
    # TITLE & SUBTITLE
    # ==========================
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(4)
    title_p.paragraph_format.space_after = Pt(2)
    trun = title_p.add_run("SplitSmart")
    trun.bold = True
    trun.font.name = 'Calibri'
    trun.font.size = Pt(24)
    trun.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(10)
    srun = sub_p.add_run("An AI-Assisted Group Expense Sharing, Trip Fund & Debt Minimization Engine")
    srun.font.name = 'Calibri'
    srun.font.size = Pt(12)
    srun.font.italic = True
    srun.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    # Submission Details Box
    sub_box = doc.add_table(rows=1, cols=1)
    sub_box.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = sub_box.cell(0, 0)
    set_cell_background(c, "F8FAFC")
    set_cell_margins(c, top=80, bottom=80, left=120, right=120)
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'<w:left w:val="single" w:sz="18" w:space="0" w:color="2563EB"/>'
        f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'</w:tcBorders>'
    )
    c._tc.get_or_add_tcPr().append(borders)
    
    bp = c.paragraphs[0]
    bp.paragraph_format.space_before = Pt(0)
    bp.paragraph_format.space_after = Pt(0)
    b_head = bp.add_run("Project Assignment Submission Details\n")
    b_head.bold = True
    b_head.font.size = Pt(10)
    b_head.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    
    b_body = bp.add_run(
        "• Course: Python Programming\n"
        "• Submitted By: [Your Name]\n"
        "• Roll Number: [Your Roll Number]\n"
        "• Department & Class: Computer Science / Engineering"
    )
    b_body.font.size = Pt(9.5)
    b_body.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================
    # 1. PROJECT OVERVIEW & PROBLEM STATEMENT
    # ==========================
    add_h1("1. Project Overview & Problem Statement")
    
    p1 = doc.add_paragraph()
    p1.add_run(
        "Managing shared expenses during vacations, flat-sharing, and group outings is notoriously prone to confusion and manual calculation errors. "
        "When multiple members pay for different expenses at different times, settling up manually leads to tangled webs of circular debts, "
        "rounding discrepancies on itemized bills, and awkward accounting for families traveling with dependent children."
    )
    
    p2 = doc.add_paragraph()
    p2.add_run(
        "SplitSmart solves this with a centralized web application combining zero-drift financial mathematics with modern AI automation. "
        "It simplifies mutual debts down to the minimum possible direct payments (at most N - 1 transactions) using a greedy bipartite algorithm, "
        "automatically rolls dependent debts onto parent sponsors, supports pre-funded group kitties, and provides fast, hands-free expense entry "
        "via Google Gemini natural text parsing and receipt photo scanning."
    )

    # ==========================
    # 2. TECHNOLOGY STACK & ARCHITECTURE (WITH VERTICAL LINES)
    # ==========================
    add_h1("2. Technology Stack & System Architecture")
    p_tech = doc.add_paragraph()
    p_tech.add_run("The application is structured into decoupled frontend, backend, database, and algorithmic layers:")

    tech_table = doc.add_table(rows=6, cols=3)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(tech_table, color="CBD5E1", sz="6")

    headers_tech = ["Layer", "Technologies Used", "Architectural Role & Key Function"]
    for i, h in enumerate(headers_tech):
        cell = tech_table.rows[0].cells[i]
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)

    tech_rows = [
        ("Frontend / UI", "HTML5, CSS3, JavaScript, Bootstrap 5", "Responsive dashboards, dynamic modal forms, live debt balance cards, and interactive dish tagging."),
        ("Backend Framework", "Python 3.10+, Flask 3.0", "RESTful routing, Blueprint modularization, session-based authentication, and request lifecycle management."),
        ("Database Layer", "MySQL 8.0+, mysql-connector-python", "ACID-compliant relational storage, foreign key cascades, and multi-threaded connection pooling."),
        ("Mathematical Engines", "Python standard library (decimal.Decimal)", "Pure decimal financial arithmetic with ROUND_HALF_UP rounding and zero-drift penny reconciliation."),
        ("Artificial Intelligence", "Google GenAI SDK (Gemini Flash), difflib", "Natural language text prompt extraction, multimodal receipt OCR parsing, and fuzzy member name matching.")
    ]

    for idx, (l, t, r_desc) in enumerate(tech_rows, start=1):
        row = tech_table.rows[idx]
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([l, t, r_desc]):
            cell = row.cells[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=55, bottom=55, left=90, right=90)
            p = cell.paragraphs[0]
            run = p.add_run(val)
            run.font.size = Pt(9)
            if c_idx == 0:
                run.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================
    # 3. UPLOADED PROJECT FILES & ROLES (WITH VERTICAL LINES)
    # ==========================
    add_h1("3. Uploaded Project Files & Roles")
    
    p_intro = doc.add_paragraph()
    p_intro.add_run("Below is the complete summary of all files included in this project submission:")

    files_summary = [
        ("run.py", "Python Script", "Application launcher: starts the Flask web server (port 5000) with environment configurations."),
        ("schema.sql", "Database DDL", "Complete MySQL schema defining users, groups, members, expenses, payers, splits, settlements, and kitty fund tables."),
        ("db.py", "Python Module", "Database connection pool manager implementing MySQL connection pooling, cursor contexts, and query runners."),
        ("app/__init__.py", "Flask App Factory", "Initializes the Flask application, configures session management, and registers all feature Blueprints."),
        ("app/config.py", "Config Script", "Central configuration reading MySQL credentials, SECRET_KEY, and GEMINI_API_KEY from environment."),
        ("app/routes/expenses.py", "Flask Blueprint", "Expense ledger controller: handles expense CRUD across Equal, Exact, %, Shares, and Itemized split modes."),
        ("app/routes/groups.py", "Flask Blueprint", "Group management controller: group creation (4 modes), invite code generation, and dashboard views."),
        ("app/routes/settlements.py", "Flask Blueprint", "Settlement controller: computes live balances, displays simplified settlement plans, and logs repayments."),
        ("app/routes/fund.py", "Flask Blueprint", "Common trip fund controller: records upfront member deposits, tracks pot balance, and computes member equity."),
        ("app/routes/ai.py", "Flask Blueprint", "AI controller: exposes endpoints for natural language text parsing and multimodal receipt OCR scanning."),
        ("services/debt_simplifier.py", "Python Service", "Core debt minimization algorithm: sorts net debtors and creditors to compute minimal bipartite settlements."),
        ("services/balance_engine.py", "Python Service", "Mathematical balance engine: computes raw net balances, family sponsor rollups, and pool equity stakes."),
        ("services/expense_service.py", "Python Service", "Transactional expense engine: multi-payer validation, split mode calculations, and atomic MySQL inserts."),
        ("services/receipt_math.py", "Python Service", "Itemized receipt math engine: distributes taxes/tips proportionally and reconciles penny-rounding drift."),
        ("services/ai_nl_parser.py", "Python Service", "Natural language parser: Gemini Flash LLM prompt extraction with fuzzy member name matching and regex fallback."),
        ("services/ai_receipt_parser.py", "Python Service", "Multimodal receipt vision parser: Gemini Vision OCR line-item and total extraction from image/PDF receipts."),
        ("templates/groups/dashboard.html", "HTML Template", "Primary group dashboard displaying net balances, simplified settlement plan, expense list, and kitty status."),
        ("static/js/main.js & nl_modal.js", "JavaScript Files", "Client-side controllers handling AJAX requests, modal form population, and AI extract triggers."),
        ("requirements.txt", "Config File", "Lists necessary Python libraries (Flask, mysql-connector-python, google-genai, Pillow, matplotlib) for one-click setup."),
        ("flowchart.png", "Image Asset", "System architecture flowchart illustrating end-to-end data ingestion, ledger persistence, and settlement pipeline."),
        ("tests/test_math_engines.py", "Unit Test Suite", "Automated test suite verifying zero-drift decimal math, penny reconciliation, sponsor rollups, and debt minimization.")
    ]

    tbl = doc.add_table(rows=len(files_summary) + 1, cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(tbl, color="CBD5E1", sz="6")
    
    headers = ["Filename", "File Type", "Description & Role in Project"]
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=70, bottom=70, left=80, right=80)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)

    for idx, (fn, ft, desc) in enumerate(files_summary, start=1):
        row = tbl.rows[idx]
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([fn, ft, desc]):
            cell = row.cells[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=50, bottom=50, left=80, right=80)
            p = cell.paragraphs[0]
            run = p.add_run(val)
            run.font.size = Pt(8.5)
            if c_idx == 0:
                run.bold = True
                run.font.name = "Consolas"
            elif c_idx == 1:
                run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================
    # 4. SYSTEM FLOWCHART & OPERATIONAL PIPELINE
    # ==========================
    add_h1("4. System Flowchart & Operational Pipeline")
    
    p_pipe = doc.add_paragraph()
    p_pipe.add_run(
        "The complete end-to-end operational workflow of the SplitSmart application is illustrated in the flowchart below:"
    )

    # Embedded Flowchart
    if os.path.exists(flowchart_img):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(flowchart_img, width=Inches(5.8))
        
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c_run = cap.add_run("Flowchart Diagram: SplitSmart End-to-End Application Workflow")
        c_run.font.name = "Calibri"
        c_run.font.size = Pt(9.5)
        c_run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
        c_run.italic = True
        cap.paragraph_format.space_after = Pt(10)

    p_wf_head = doc.add_paragraph()
    p_wf_head.paragraph_format.space_before = Pt(4)
    p_wf_head.paragraph_format.space_after = Pt(4)
    r_wf = p_wf_head.add_run("Brief Workflow Summary:")
    r_wf.bold = True
    r_wf.font.size = Pt(10)

    wf_points = [
        ("1. Group Setup: ", "Users register, create/join groups with unique invite codes, and select funding modes (Individual vs Kitty Pool)."),
        ("2. Expense Ingestion: ", "Expenses enter via manual forms (Equal, Exact, %, Shares, Itemized), AI text parsing, or receipt photo OCR."),
        ("3. Ledger Persistence: ", "Records commit atomically to MySQL with proportional tax/tip math and zero-drift penny reconciliation."),
        ("4. Balance Routing & Rollups: ", "Kitty pool expenses deduct from the pot; individual expenses compute net balances, folding child debts onto parent sponsors."),
        ("5. Debt Settlement: ", "Greedy bipartite matching minimizes mutual debts into at most N - 1 direct payments settled via Cash or UPI.")
    ]

    for title, desc in wf_points:
        p_pt = doc.add_paragraph()
        p_pt.paragraph_format.left_indent = Inches(0.2)
        p_pt.paragraph_format.space_after = Pt(3.5)
        rt = p_pt.add_run(f"• {title}")
        rt.bold = True
        rt.font.size = Pt(9.5)
        rd = p_pt.add_run(desc)
        rd.font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================
    # 5. HOW TO RUN THE PROGRAM (STEP-BY-STEP)
    # ==========================
    add_h1("5. How to Run the Program (Step-by-Step Guide)")
    
    p_run_intro = doc.add_paragraph()
    p_run_intro.add_run(
        "The project is completely self-contained. The database schema (schema.sql), full Flask backend, and automated "
        "test suites are included and ready to run immediately on any Windows, macOS, or Linux PC."
    )

    add_h2("Prerequisites & Environment Setup")
    p_pre = doc.add_paragraph()
    p_pre.add_run(
        "• Python: Python 3.10 or higher installed on your PC.\n"
        "• MySQL Server: MySQL 8.0+ or MariaDB (via XAMPP / WampServer) running locally.\n"
        "• Virtual Environment Note: Setting up a virtual environment (venv) is standard practice to isolate project libraries, "
        "but running directly in your existing Python environment via pip install -r requirements.txt is also fully supported.\n"
        "• Environment Variables (.env): Database credentials and secret keys are stored in .env in the project root."
    )

    # Step 1
    add_h2("Step 1: Open the Project Directory in Terminal")
    p = doc.add_paragraph()
    p.add_run("Extract the submission zip file to any folder on your computer. Open terminal/command prompt and navigate into the folder:")
    add_code_box(doc, "cd path/to/SplitSmart")

    # Step 2
    add_h2("Step 2: (Optional but Recommended) Setup a Virtual Environment")
    p = doc.add_paragraph()
    p.add_run("To isolate dependencies, create and activate a clean virtual environment:")
    add_code_box(doc, "# Windows:\npython -m venv venv\nvenv\\Scripts\\activate\n\n# macOS / Linux:\npython3 -m venv venv\nsource venv/bin/activate")

    # Step 3
    add_h2("Step 3: Database Setup (Create Database & Import Schema)")
    p = doc.add_paragraph()
    p.add_run("In your MySQL client (phpMyAdmin, Workbench, or command line), create the database and import schema.sql:")
    add_code_box(doc, "CREATE DATABASE splitsmart_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n\n# Import schema via terminal (or use phpMyAdmin 'Import' tab):\nmysql -u root -p splitsmart_db < schema.sql")

    # Step 4
    add_h2("Step 4: Configure Database Credentials (.env)")
    p = doc.add_paragraph()
    p.add_run("Ensure the .env file in the root folder matches your local MySQL setup (default root with blank password works for XAMPP):")
    add_code_box(doc, "DB_HOST=127.0.0.1\nDB_PORT=3306\nDB_USER=root\nDB_PASSWORD=\nDB_NAME=splitsmart_db\nSECRET_KEY=splitsmart-dev-secret-key-123\nGEMINI_API_KEY=   # Optional: Add key, or leave blank to use automatic offline fallbacks")

    # Step 5
    add_h2("Step 5: Install Required Dependencies")
    p = doc.add_paragraph()
    p.add_run("Run the following command to install the required Python libraries:")
    add_code_box(doc, "pip install -r requirements.txt")

    # Step 6
    add_h2("Step 6: (Optional) Run Automated Mathematical Test Suites")
    p = doc.add_paragraph()
    p.add_run("Verify that zero-drift decimal arithmetic, debt minimization, and sponsor rollups pass all unit tests:")
    add_code_box(doc, "python -m unittest tests/test_math_engines.py\n# Output: Ran 4 tests ... OK")

    # Step 7
    add_h2("Step 7: Launch the Web Application")
    p = doc.add_paragraph()
    p.add_run("Start the interactive Flask web server with:")
    add_code_box(doc, "python run.py")
    p_launch = doc.add_paragraph()
    p_launch.add_run("The server will start at: http://127.0.0.1:5000. Open your browser and navigate to the link to register, create groups, and start managing expenses.")

    # ==========================
    # 6. CORE ALGORITHMS & LOGIC (IN BRIEF)
    # ==========================
    add_h1("6. Core Mathematical Logic & Algorithms (In Brief)")

    add_h2("6.1 Greedy Bipartite Debt Minimization")
    p = doc.add_paragraph()
    p.add_run(
        "Computes each member's net balance (Total Paid - Total Owed) and greedily matches the largest debtor with the largest creditor. "
        "This settles at least one participant per step, provably compressing complex mutual debts into at most N - 1 direct payments."
    )

    # Embed Algorithm Flowchart
    debt_flowchart_img = os.path.join(base_dir, "scripts", "debt_minimization_flowchart.png")
    if os.path.exists(debt_flowchart_img):
        p_img_algo = doc.add_paragraph()
        p_img_algo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img_algo.paragraph_format.space_before = Pt(4)
        p_img_algo.paragraph_format.space_after = Pt(2)
        r_algo = p_img_algo.add_run()
        r_algo.add_picture(debt_flowchart_img, width=Inches(5.0))
        
        cap_algo = doc.add_paragraph()
        cap_algo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c_algo = cap_algo.add_run("Flowchart: Greedy Bipartite Debt Minimization Steps")
        c_algo.font.name = "Calibri"
        c_algo.font.size = Pt(8.5)
        c_algo.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
        c_algo.italic = True
        cap_algo.paragraph_format.space_after = Pt(6)

    add_h2("6.2 Family Unit & Dependent Rollup Engine")
    p = doc.add_paragraph()
    p.add_run(
        "Uses a cycle-safe sponsor_id hierarchy to automatically roll child debts onto their designated parent sponsor. "
        "Dependents always maintain an exact ₹0.00 settlement balance, allowing parents to settle a single consolidated net amount."
    )

    add_h2("6.3 Proportional Itemized Split Engine & Penny Reconciliation")
    p = doc.add_paragraph()
    p.add_run(
        "Divides individual dishes among tagged eaters and distributes taxes, tips, and discounts proportionally based on dish subtotals. "
        "An automated zero-drift reconciler assigns any residual rounding penny to the top spender, guaranteeing 100% exact bill conservation."
    )

    add_h2("6.4 Common Kitty Pool (Trip Fund) Accounting")
    p = doc.add_paragraph()
    p.add_run(
        "Manages collective upfront trip funds by deducting group expenses directly from the pot. "
        "Member equity stakes (Contribution - Consumption) are continuously tracked, triggering instant deficit alerts if any member overspends."
    )

    # ==========================
    # 7. TESTING & VERIFICATION (IN BRIEF)
    # ==========================
    add_h1("7. Testing & Verification (In Brief)")
    p_test = doc.add_paragraph()
    p_test.add_run(
        "The project includes an automated test suite (tests/test_math_engines.py) that validates all core mathematical models. "
        "Executing the tests via terminal (python -m unittest tests/test_math_engines.py) confirms 100% pass status across four essential scenarios:\n"
        "• Itemized Receipt Splitting: Validates that member shares sum to the exact bill total (₹134.35) with zero penny drift across 4 dishes with tax, tip, and discount.\n"
        "• Net Balance Conservation: Asserts that sum(B_i) == 0.00 across multiple out-of-pocket payers, splits, and intermediate repayments.\n"
        "• Family Sponsor Rollups: Verifies that child credits and debts roll onto the parent sponsor, leaving children at exactly 0.00.\n"
        "• Debt Minimization: Confirms that a dense 4-member debt web settles completely in at most 3 direct transactions (down from 6 naive debts)."
    )

    # ==========================
    # 8. VISUAL RESULTS & APPLICATION SCREENSHOTS
    # ==========================
    add_h1("8. Visual Results & Application Screenshots")
    
    p_vis = doc.add_paragraph()
    p_vis.add_run(
        "This section presents the primary user interfaces and workflow stages of the SplitSmart application, "
        "including user authentication, group balance tracking, multi-mode expense creation, AI text parsing, and trip fund pool monitoring."
    )

    add_figure_text(doc, 1, "User Login and Registration Interface")
    add_figure_text(doc, 2, "Group Dashboard with Member Balances & Simplified Settlement Plan")
    add_figure_text(doc, 3, "Expense Addition Modal (Equal, Exact, and Itemized Splits)")
    add_figure_text(doc, 4, "AI Natural Language Expense Parser in Action")
    add_figure_text(doc, 5, "Common Kitty (Trip Fund) Pool Status & Equity Breakdown")

    # ==========================
    # 9. CONCLUSION
    # ==========================
    add_h1("9. Conclusion")
    p_concl = doc.add_paragraph()
    p_concl.add_run(
        "The SplitSmart application provides a practical, mathematically verified, and AI-enhanced approach to group expense management. "
        "By replacing complex circular debts with an optimal greedy bipartite minimization algorithm, providing seamless family dependent rollups, "
        "guaranteeing zero-drift penny reconciliation, and automating data entry via Google Gemini AI, the system gives users complete financial "
        "transparency and confidence when settling up shared expenses."
    )

    # Save dynamically to first available unlocked file name
    candidate_names = [
        "SplitSmart_Submission_CleanFigures.docx",
        "SplitSmart_Project_Report_Concise.docx",
        "SplitSmart_Project_Report_Final.docx",
        "SplitSmart_Final_Submission.docx",
        "SplitSmart_Submission_Report_v3.docx",
        "SplitSmart_Submission_Report_v2.docx",
        "SplitSmart_Submission_Report.docx"
    ]
    saved_path = None
    for name in candidate_names:
        p = os.path.abspath(os.path.join(base_dir, name))
        try:
            doc.save(p)
            print(f"Successfully saved report to: {p}")
            if not saved_path:
                saved_path = p
        except PermissionError:
            pass
    if not saved_path:
        fallback = os.path.abspath(os.path.join(base_dir, "SplitSmart_Report_Latest.docx"))
        doc.save(fallback)
        print(f"Saved report to fallback: {fallback}")

if __name__ == "__main__":
    generate_report()
