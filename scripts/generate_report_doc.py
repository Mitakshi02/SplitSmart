"""
Generate SplitSmart Project Report (.docx)
Refined per user instructions:
- Clean, high-level Project Overview without feature lists.
- File inventory presented purely as a clean table (no redundant text paragraphs).
- Brief, punchy explanations for algorithms with clean indentations and breathing room.
- Flowchart image displayed prominently with spacious, well-indented accompanying points.
- Evaluator steps and 5 screenshot placeholders preserved cleanly.
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

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Sets internal padding for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for margin_name, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{margin_name}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_callout_box(doc, text, caption):
    """Creates a distinct screenshot placeholder box."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=220, bottom=220, left=260, right=260)
    
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="10" w:space="0" w:color="CBD5E1"/>'
        f'<w:bottom w:val="single" w:sz="10" w:space="0" w:color="CBD5E1"/>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="2563EB"/>'
        f'<w:right w:val="single" w:sz="10" w:space="0" w:color="CBD5E1"/>'
        f'</w:tcBorders>'
    )
    cell._tc.get_or_add_tcPr().append(borders)
    
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run1 = p.add_run(f"\n📷 {text}\n")
    run1.bold = True
    run1.font.name = "Calibri"
    run1.font.size = Pt(11)
    run1.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    
    run2 = p.add_run("[ Paste your website screenshot here in Word ]\n")
    run2.italic = True
    run2.font.name = "Calibri"
    run2.font.size = Pt(9.5)
    run2.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_run = cap_p.add_run(f"Figure: {caption}")
    cap_run.font.name = "Calibri"
    cap_run.font.size = Pt(9.5)
    cap_run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    cap_run.italic = True
    cap_p.paragraph_format.space_before = Pt(3)
    cap_p.paragraph_format.space_after = Pt(14)

def add_embedded_image(doc, img_path, caption, width_in=6.0):
    """Embeds an image centered with clean spacing and caption."""
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run()
        run.add_picture(img_path, width=Inches(width_in))
        
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c_run = cap.add_run(f"Figure: {caption}")
        c_run.font.name = "Calibri"
        c_run.font.size = Pt(9.5)
        c_run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
        c_run.italic = True
        cap.paragraph_format.space_after = Pt(12)

def build_report():
    doc = docx.Document()
    
    # 1-inch margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys_flowchart_path = os.path.join(base_dir, "scripts", "system_workflow_flowchart.png")
    debt_flowchart_path = os.path.join(base_dir, "scripts", "debt_minimization_flowchart.png")

    # ==========================
    # TITLE & HEADER
    # ==========================
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(6)
    title_p.paragraph_format.space_after = Pt(2)
    title_run = title_p.add_run("SplitSmart")
    title_run.bold = True
    title_run.font.name = 'Calibri'
    title_run.font.size = Pt(26)
    title_run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(14)
    sub_run = sub_p.add_run("Group Expense Sharing, Trip Fund & Debt Minimization Web Application")
    sub_run.font.name = 'Calibri'
    sub_run.font.size = Pt(13)
    sub_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

    # Metadata Table
    meta_tbl = doc.add_table(rows=4, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Project Name:", "SplitSmart Web Application"),
        ("Course / Assignment:", "Project Assignment Submission"),
        ("Technology Stack:", "Python 3, Flask, MySQL, Bootstrap 5, Google Gemini AI"),
        ("Submission Date:", "October 2026")
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        row = meta_tbl.rows[row_idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.0)
        c1.width = Inches(4.5)
        set_cell_background(c0, "F1F5F9")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=50, bottom=50, left=90, right=90)
        set_cell_margins(c1, top=50, bottom=50, left=90, right=90)
        
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        r0.bold = True
        r0.font.size = Pt(9.5)
        
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        r1.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Headings Helpers
    def add_h1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(5)
        r = h.add_run(text)
        r.bold = True
        r.font.name = 'Calibri'
        r.font.size = Pt(15)
        r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(11)
        h.paragraph_format.space_after = Pt(3)
        r = h.add_run(text)
        r.bold = True
        r.font.name = 'Calibri'
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8)
        return h

    # ==========================
    # SECTION 1: PROJECT OVERVIEW (NATURAL, NO FEATURE BULLETS)
    # ==========================
    add_h1("1. Project Overview & Motivation")
    
    p1 = doc.add_paragraph()
    p1.paragraph_format.space_after = Pt(6)
    p1.add_run(
        "SplitSmart is a web application created to simplify the often confusing process of tracking and settling "
        "shared expenses among friends, flatmates, colleagues, and travel groups. During any group trip or shared living "
        "situation, multiple people pay for different items—hotels, travel tickets, food, fuel, and supplies. "
        "Keeping track of who paid for what and figuring out who owes whom at the end of the trip quickly turns into "
        "a messy, error-prone chore."
    )
    
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(10)
    p2.add_run(
        "In addition, standard expense sharing scenarios often have practical complexities that existing tools ignore: "
        "groups with families where children's expenses should naturally fall under a parent, trips funded through an upfront "
        "common cash kitty rather than individual out-of-pocket payments, and restaurant bills where taxes and tips need "
        "to be split fairly based on what each person ordered. The goal of SplitSmart is to provide a single, transparent, "
        "and automated platform that handles these scenarios cleanly, minimizes the number of repayments needed, and provides "
        "fast expense entry so group members can settle their dues without arguments or manual calculations."
    )

    # ==========================
    # SECTION 2: TECH STACK
    # ==========================
    add_h1("2. Technology Stack")
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run("The application is built on a modular architecture using the following core technologies:")

    tech_table = doc.add_table(rows=6, cols=3)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Layer", "Technologies", "Role in Project"]
    for i, h in enumerate(headers):
        cell = tech_table.rows[0].cells[i]
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)

    tech_rows = [
        ("Frontend", "HTML5, CSS3, JavaScript, Bootstrap 5", "User interfaces, responsive group dashboards, interactive modal forms, and dynamic balance cards."),
        ("Backend", "Python 3.10+, Flask 3.0", "Application routing, Blueprint structure, session authentication, and REST API endpoints."),
        ("Database", "MySQL 8.0+, mysql-connector-python", "Relational storage, connection pooling, ACID transaction support, and foreign key integrity."),
        ("Financial Math", "Python standard library (decimal.Decimal)", "Pure decimal currency calculations with ROUND_HALF_UP rounding and zero-drift penny reconciliation."),
        ("AI Integrations", "Google GenAI SDK (Gemini Flash), difflib", "Natural language text expense extraction, multimodal receipt OCR scanning, and fuzzy name matching.")
    ]

    for idx, (l, t, r_desc) in enumerate(tech_rows, start=1):
        row = tech_table.rows[idx]
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([l, t, r_desc]):
            cell = row.cells[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=90, right=90)
            p = cell.paragraphs[0]
            run = p.add_run(val)
            run.font.size = Pt(9)
            if c_idx == 0:
                run.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================
    # SECTION 3: SYSTEM WORKFLOW & FLOWCHART
    # ==========================
    add_h1("3. System Workflow & Flowchart")

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run(
        "The flowchart below illustrates the end-to-end data and process flow of the SplitSmart application, "
        "tracing the journey from user onboarding and expense recording through mathematical processing, "
        "family rollup, and final debt settlement:"
    )

    # Embedded Flowchart Image
    add_embedded_image(doc, sys_flowchart_path, "SplitSmart End-to-End Application Workflow Flowchart", width_in=6.0)

    p_wf = doc.add_paragraph()
    p_wf.paragraph_format.space_before = Pt(4)
    p_wf.paragraph_format.space_after = Pt(6)
    p_wf.add_run("Key Stages of the Workflow:")

    stages = [
        ("1. User Access & Setup:", " Users register or log in, then create or join a group via a unique 8-character invite code. Groups choose an operating mode (Quick, Regular, Friends, Family) and funding mode (Individual or Pooled Kitty)."),
        ("2. Expense Ingestion:", " Expenses enter the system through three flexible options—manual entry (Equal, Exact, Percentage, Shares, or Itemized), AI natural text parsing (typing a sentence), or AI receipt scanning (uploading a bill photo)."),
        ("3. Transaction Persistence:", " Expenses are saved atomically across expenses, payers, and splits tables with zero-drift decimal reconciliation so every penny matches."),
        ("4. Funding Mode Branch:", " If a Common Kitty is used, funds are deducted from the central pot and individual equity is tracked. If Individual mode is used, net balances are computed."),
        ("5. Family Rollup:", " In family groups, children's debts automatically roll up to their sponsor parent, guaranteeing children maintain a 0.00 settlement balance."),
        ("6. Debt Simplification:", " The greedy bipartite algorithm matches debtors and creditors, reducing complicated cross-debts to the absolute minimum number of direct repayments."),
        ("7. Settlement:", " Members record peer-to-peer repayments (Cash/UPI) until all active balances reach zero.")
    ]

    for title, desc in stages:
        sp = doc.add_paragraph()
        sp.paragraph_format.left_indent = Inches(0.25)
        sp.paragraph_format.space_after = Pt(4)
        r_t = sp.add_run(title)
        r_t.bold = True
        r_t.font.size = Pt(9.5)
        r_d = sp.add_run(desc)
        r_d.font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================
    # SECTION 4: FILE INVENTORY (TABLE ONLY)
    # ==========================
    add_h1("4. Project File Inventory")
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run("The table below details all files included in the project submission along with their directory location and specific role:")

    files_data = [
        ("run.py", "Root", "Application launcher. Configures host, port (5000), debug settings, and starts the Flask server."),
        ("db.py", "Root", "Database connection pool manager. Implements MySQL connection pooling, context managers, and execute_query / execute_write helpers."),
        ("schema.sql", "Root", "Complete MySQL schema DDL. Creates tables for users, groups, members, expenses, payers, splits, settlements, fund contributions, and receipts."),
        ("requirements.txt", "Root", "Dependencies specification listing Flask, mysql-connector-python, google-genai, Pillow, python-dotenv, and matplotlib."),
        (".env / .env.example", "Root", "Configuration file declaring MySQL credentials, SECRET_KEY, and optional GEMINI_API_KEY."),
        ("audit_dashboard.py", "Root", "CLI utility script allowing administrators to inspect database records, groups, and ledger integrity from terminal."),
        ("app/__init__.py", "app/", "Application factory module. Initializes Flask, registers blueprints, and sets up custom 404/500 error pages."),
        ("app/config.py", "app/", "Reads environment configuration settings with default fallbacks for file uploads and MySQL pool limits."),
        ("app/db.py", "app/", "Bridge module re-exporting connection pool utilities for application routes."),
        ("app/routes/auth.py", "app/routes/", "Handles user registration, password hashing (PBKDF2), login authentication, and logout session clearing."),
        ("app/routes/groups.py", "app/routes/", "Manages group creation, invite code claims, member onboarding, and main group dashboard rendering."),
        ("app/routes/expenses.py", "app/routes/", "API routes for creating, listing, viewing, and deleting expenses across all split modes."),
        ("app/routes/settlements.py", "app/routes/", "Routes for fetching live member balances, viewing simplified settlement plans, and recording repayments."),
        ("app/routes/fund.py", "app/routes/", "Common trip fund routes for recording upfront member deposits, tracking kitty balance, and viewing equity."),
        ("app/routes/ai.py", "app/routes/", "Endpoints for natural language prompt parsing (/ai/parse-nl) and receipt OCR scanning (/ai/scan-receipt)."),
        ("services/balance_engine.py", "services/", "Pure decimal financial math engine computing raw balances, family sponsor debt rollups, and kitty pool equity."),
        ("services/debt_simplifier.py", "services/", "Greedy bipartite debt minimization algorithm reducing cross-debts to minimum direct repayments (<= N-1)."),
        ("services/expense_service.py", "services/", "Transactional expense service validating multi-payer contributions, split math, and atomic database commits."),
        ("services/settlement_service.py", "services/", "Live balance aggregator fetching expenses, applying rollups, and generating human-readable settlement plans."),
        ("services/pool_service.py", "services/", "Common trip fund service handling contributions, fund deductions, member equity, and deficit warnings."),
        ("services/receipt_math.py", "services/", "Itemized receipt math engine distributing taxes/tips/discounts proportionally with penny-level rounding reconciliation."),
        ("services/ai_nl_parser.py", "services/", "Extracts expense fields from text using Gemini Flash with fuzzy member name matching and regex fallback."),
        ("services/ai_receipt_parser.py", "services/", "Multimodal receipt vision parser extracting line items, dishes, prices, and totals from image/PDF receipts."),
        ("services/ai_receipt_scanner.py", "services/", "Extended OCR normalizer standardizing dish names, missing prices, and decimal formatting."),
        ("services/auth_service.py", "services/", "User authentication service implementing registration, password verification, and @login_required decorator."),
        ("services/group_service.py", "services/", "Group administration service managing invite codes, member roles, guest placeholders, and sponsor_id links."),
        ("blueprints/*.py", "blueprints/", "Bridge export modules providing clean re-exports for application blueprints."),
        ("templates/base.html", "templates/", "Master HTML layout with responsive navigation, notifications, modal containers, and styling."),
        ("templates/groups/dashboard.html", "templates/", "Primary group dashboard displaying net balances, simplified settlement plan, expense list, and kitty status."),
        ("templates/groups/create.html", "templates/", "Group creation form allowing users to configure operating modes and funding modes."),
        ("templates/auth/login.html & register.html", "templates/", "Authentication pages for account creation and login."),
        ("static/js/main.js & nl_modal.js", "static/js/", "Frontend JavaScript controlling dynamic forms, modal triggers, and AI parsing requests."),
        ("static/css/style.css", "static/css/", "Custom styling for cards, badges, financial color indicators, and layout."),
        ("tests/test_math_engines.py", "tests/", "Unit test suite verifying decimal precision, penny reconciler, debt minimization, and family rollups."),
        ("tests/test_expenses_and_settlements.py", "tests/", "Integration test suite validating expense creation and settlement execution against the database.")
    ]

    file_tbl = doc.add_table(rows=len(files_data) + 1, cols=3)
    file_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(["File Name", "Directory", "Role & Core Responsibility"]):
        cell = file_tbl.rows[0].cells[i]
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=70, bottom=70, left=80, right=80)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)

    for idx, (fn, loc, desc) in enumerate(files_data, start=1):
        row = file_tbl.rows[idx]
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([fn, loc, desc]):
            cell = row.cells[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=50, bottom=50, left=80, right=80)
            p = cell.paragraphs[0]
            run = p.add_run(val)
            run.font.size = Pt(8.5)
            if c_idx == 0:
                run.bold = True
                run.font.name = "Consolas"

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================
    # SECTION 5: ALGORITHMS (BRIEF & PUNCHY)
    # ==========================
    add_h1("5. Core Algorithms & Mathematical Logic (In Brief)")

    add_h2("5.1 Greedy Bipartite Debt Minimization")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.add_run(
        "Instead of keeping dozens of confusing pairwise debts between individual members, SplitSmart calculates "
        "each member's net balance (Total Paid - Total Owed). Members are then separated into Debtors (negative balance) "
        "and Creditors (positive balance). By sorting both lists in descending order and greedily pairing the largest debtor "
        "with the largest creditor, the algorithm settles all balances in at most N - 1 transactions."
    )

    # Embedded Debt Minimization Flowchart
    add_embedded_image(doc, debt_flowchart_path, "Greedy Bipartite Debt Minimization Flow", width_in=5.6)

    add_h2("5.2 Family Unit & Dependent Rollup")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.add_run(
        "To handle family trips without awkward accounting for children, members can have a sponsor_id linking them to "
        "an adult. The balance engine traverses this hierarchy, folding all dependent debts directly into the sponsor's net balance. "
        "This ensures dependents always show a clean 0.00 settlement balance, and parents receive a single consolidated settlement figure."
    )

    add_h2("5.3 Proportional Itemized Splitting & Penny Reconciliation")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.add_run(
        "When splitting restaurant receipts, individual dishes are divided among the members who shared them. "
        "Shared overheads (taxes, tips, delivery fees, minus discounts) are distributed proportionally based on each person's "
        "dish subtotal. Because 2-decimal financial rounding can occasionally produce an off-by-one penny difference, "
        "our zero-drift reconciler detects the discrepancy and assigns it to the highest spender, guaranteeing that "
        "the sum of all member shares matches the receipt total to the exact cent."
    )

    add_h2("5.4 Common Kitty Pool (Trip Fund) Accounting")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.add_run(
        "For trips funded through an upfront pool, members deposit cash into a shared kitty. Expenses paid from the kitty "
        "bypass peer-to-peer debts and directly decrement the central pot. The system tracks each member's equity "
        "(Contribution - Consumption). If a member consumes more than they contributed, the system flags a deficit warning."
    )

    # ==========================
    # SECTION 6: INSTALLATION GUIDE
    # ==========================
    add_h1("6. Step-by-Step Installation & Execution Guide")
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.add_run("Follow these straightforward steps to run the application on any standard computer:")

    steps = [
        ("Step 1: Check Prerequisites", "Ensure Python 3.10+ and a MySQL server (native or XAMPP) are installed and running."),
        ("Step 2: Create the Database", "In your MySQL client, run:\nCREATE DATABASE splitsmart_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"),
        ("Step 3: Import Schema", "Import schema.sql into splitsmart_db via phpMyAdmin or terminal:\nmysql -u root -p splitsmart_db < schema.sql"),
        ("Step 4: Configure .env", "Check .env in the project root to ensure DB_USER and DB_PASSWORD match your local MySQL setup (default root with blank password works for XAMPP)."),
        ("Step 5: Install Requirements", "In your terminal, navigate to the project directory and run:\npip install -r requirements.txt"),
        ("Step 6: Run Test Suite (Optional)", "Verify math engines by running:\npython -m unittest tests/test_math_engines.py\n(All tests will pass with OK)."),
        ("Step 7: Start the Server", "Launch the web app with:\npython run.py\nThe terminal will show: Server running at: http://127.0.0.1:5000/"),
        ("Step 8: Open in Browser", "Open your web browser and go to http://127.0.0.1:5000 to register an account, create a group, and start using SplitSmart!")
    ]

    for s_title, s_desc in steps:
        sp = doc.add_paragraph()
        sp.paragraph_format.left_indent = Inches(0.2)
        sp.paragraph_format.space_after = Pt(4)
        rt = sp.add_run(f"• {s_title}: ")
        rt.bold = True
        rt.font.size = Pt(9.5)
        rd = sp.add_run(s_desc)
        rd.font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================
    # SECTION 7: SCREENSHOTS PLACEHOLDERS
    # ==========================
    add_h1("7. Application Screenshots (Visual Verification)")
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.add_run("Paste your running application screenshots into the designated frames below:")

    add_callout_box(doc, "SCREENSHOT 1: User Login & Registration Page", "User authentication interface.")
    add_callout_box(doc, "SCREENSHOT 2: Group Dashboard & Net Balances", "Dashboard showing live balances and simplified settlement plan.")
    add_callout_box(doc, "SCREENSHOT 3: Expense Creation Modal", "Modal form with Equal, Exact, Percentage, Shares, and Itemized split options.")
    add_callout_box(doc, "SCREENSHOT 4: AI Natural Language Expense Parser", "AI prompt modal extracting expense details from plain text.")
    add_callout_box(doc, "SCREENSHOT 5: Common Kitty (Trip Fund) Overview", "Common fund view displaying member contributions, expenses, and remaining equity.")

    # ==========================
    # SECTION 8: TESTING & CONCLUSION
    # ==========================
    add_h1("8. Testing & Verification")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run(
        "The project includes automated unit and integration test suites in the tests/ folder. "
        "These tests verify decimal arithmetic precision, ensure the penny reconciler prevents rounding drift, "
        "confirm that children's balances roll up to parents leaving children at 0.00, and assert that the debt minimizer "
        "provably settles all mutual balances in the fewest possible transactions."
    )

    add_h1("9. Conclusion")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run(
        "SplitSmart provides a complete, modern solution to group expense management. By combining reliable "
        "financial math with practical features like family rollups, common trip funds, itemized bill splitting, "
        "and AI text/receipt parsing, it eliminates confusion and simplifies settling up for everyone."
    )

    # Save document
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SplitSmart_Project_Report.docx"))
    try:
        doc.save(output_path)
        print(f"Refined report successfully generated at: {output_path}")
    except PermissionError:
        alt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SplitSmart_Project_Report_Updated.docx"))
        doc.save(alt_path)
        print(f"Original file was open in Word. Saved refined report to: {alt_path}")

if __name__ == "__main__":
    build_report()

