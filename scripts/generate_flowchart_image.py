"""
Refined High-Resolution Flowchart Generator for SplitSmart.
Generates:
1. scripts/flowchart.png (Clean, vibrant vertical end-to-end workflow flowchart)
2. scripts/debt_minimization_flowchart.png (Compact algorithmic step flowchart)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

def generate_vertical_workflow_flowchart(output_path):
    # Proportions: 10 x 14.5 inches at 300 DPI for ultra-crisp display in Word
    fig, ax = plt.subplots(figsize=(10, 14.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 145)
    ax.axis('off')

    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')

    # Color Palette
    C_HEADER = '#1E3A8A'    # Deep Navy
    C_AUTH   = '#2563EB'    # Royal Blue
    C_GROUP  = '#0D9488'    # Teal
    C_MANUAL = '#3B82F6'    # Blue
    C_AI_TXT = '#7C3AED'    # Purple
    C_AI_OCR = '#9333EA'    # Violet
    C_COMMIT = '#D97706'    # Amber / Orange
    C_KITTY  = '#EA580C'    # Orange
    C_P2P    = '#0284C7'    # Sky Blue
    C_FAMILY = '#E11D48'    # Rose
    C_DEBT   = '#059669'    # Emerald Green
    C_SETTLE = '#1D4ED8'    # Deep Blue

    # Main Title
    ax.text(50, 141, "SplitSmart: End-to-End Application Workflow Flowchart", 
            ha='center', va='center', fontsize=16, fontweight='bold', color=C_HEADER)
    ax.text(50, 137.5, "From User Authentication to Ledger Persistence, Family Rollups & Debt Minimization", 
            ha='center', va='center', fontsize=9.5, fontstyle='italic', color='#64748B')

    # Helper function to draw rounded box with shadow
    def draw_box(x, y, w, h, title, subtitle, color, text_color='#FFFFFF', sub_color='#E2E8F0'):
        # Subtle Drop Shadow
        shadow = FancyBboxPatch((x - w/2 + 0.35, y - h/2 - 0.35), w, h,
                                boxstyle="round,pad=0.7,rounding_size=1.2",
                                facecolor='#CBD5E1', edgecolor='none', zorder=2)
        ax.add_patch(shadow)

        # Main Box
        box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                             boxstyle="round,pad=0.7,rounding_size=1.2",
                             facecolor=color, edgecolor='#0F172A', linewidth=1.1,
                             zorder=3)
        ax.add_patch(box)

        # Title & Subtitle
        if subtitle:
            ax.text(x, y + 1.2, title, ha='center', va='center', 
                    fontsize=9.8, fontweight='bold', color=text_color, zorder=4)
            ax.text(x, y - 1.6, subtitle, ha='center', va='center', 
                    fontsize=7.8, color=sub_color, zorder=4)
        else:
            ax.text(x, y, title, ha='center', va='center', 
                    fontsize=10, fontweight='bold', color=text_color, zorder=4)

    # Helper function to draw arrow
    def draw_arrow(x1, y1, x2, y2, label=None, label_side='right', color='#475569'):
        arrow = FancyArrowPatch((x1, y1), (x2, y2),
                                arrowstyle="-|>,head_length=4.5,head_width=2.8",
                                connectionstyle="arc3,rad=0",
                                color=color, linewidth=1.4, zorder=2)
        ax.add_patch(arrow)
        if label:
            lx = (x1 + x2) / 2
            ly = (y1 + y2) / 2
            offset = 1.8 if label_side == 'right' else -1.8
            ax.text(lx + offset, ly, label, ha='center', va='center', 
                    fontsize=7.5, fontweight='bold', color='#0F172A',
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="#CBD5E1", alpha=0.95),
                    zorder=5)

    # Helper function for decision diamond
    def draw_diamond(x, y, w, h, text, color='#4F46E5'):
        # shadow
        sh_pts = [[x + 0.35, y + h/2 - 0.35], [x + w/2 + 0.35, y - 0.35], [x + 0.35, y - h/2 - 0.35], [x - w/2 + 0.35, y - 0.35]]
        sh = patches.Polygon(sh_pts, closed=True, facecolor='#CBD5E1', edgecolor='none', zorder=2)
        ax.add_patch(sh)

        pts = [[x, y + h/2], [x + w/2, y], [x, y - h/2], [x - w/2, y]]
        poly = patches.Polygon(pts, closed=True, facecolor=color, edgecolor='#0F172A', linewidth=1.1, zorder=3)
        ax.add_patch(poly)
        ax.text(x, y, text, ha='center', va='center', fontsize=8.8, fontweight='bold', color='#FFFFFF', zorder=4)

    # 1. Start Node: User Registration
    draw_box(50, 131, 38, 5.2, "1. USER REGISTRATION & AUTHENTICATION", "Session token, PBKDF2 Password Hashing, RBAC", C_AUTH)

    # Arrow 1 -> 2
    draw_arrow(50, 128.4, 50, 122.6)

    # 2. Group Setup
    draw_box(50, 119.5, 46, 6.2, "2. GROUP INITIALIZATION & ONBOARDING", 
             "Select Mode (Quick, Regular, Friends, Family) & Funding (Individual / Kitty)\nInvite Code Generation & Member/Guest Linking", C_GROUP)

    # Arrow 2 -> Diamond 1
    draw_arrow(50, 116.4, 50, 109.5)

    # Diamond 1: Expense Pathway
    draw_diamond(50, 105, 30, 8.5, "EXPENSE ENTRY\nPATHWAY?", '#4F46E5')

    # Path A: Left - Manual
    draw_arrow(35, 105, 18, 105)
    draw_arrow(18, 105, 18, 95, "Manual Entry", 'left')
    draw_box(18, 91.5, 28, 7.0, "PATH A: MANUAL LEDGER", 
             "Equal, Exact, Percentage, Shares\nMulti-payer selection & splits", C_MANUAL)

    # Path B: Center - AI Text
    draw_arrow(50, 100.75, 50, 95, "Natural Text", 'right')
    draw_box(50, 91.5, 28, 7.0, "PATH B: AI TEXT EXTRACT", 
             "Gemini Flash + Fuzzy Name Match\nRegex fallback -> Form Autofill", C_AI_TXT)

    # Path C: Right - AI Receipt
    draw_arrow(65, 105, 82, 105)
    draw_arrow(82, 105, 82, 95, "Receipt OCR", 'right')
    draw_box(82, 91.5, 28, 7.0, "PATH C: AI RECEIPT SCANNER", 
             "Gemini Vision itemization\nDish prices, Tax, Tip & Dish Tagging", C_AI_OCR)

    # Convergence to Transaction Commit
    draw_arrow(18, 88.0, 40, 79.5)
    draw_arrow(50, 88.0, 50, 79.5)
    draw_arrow(82, 88.0, 60, 79.5)

    # 3. Transaction Commit & Penny Reconciler
    draw_box(50, 76.5, 48, 6.2, "3. TRANSACTION COMMIT & PENNY RECONCILIATION", 
             "Atomic MySQL insert into expenses, expense_payers, expense_splits\nItemized split: Overhead distribution + zero-drift penny reconciler", C_COMMIT)

    # Arrow 3 -> Diamond 2
    draw_arrow(50, 73.4, 50, 67.5)

    # Diamond 2: Funding Mode
    draw_diamond(50, 63, 28, 8.5, "FUNDING\nMODE?", '#F59E0B')

    # Branch Left: Kitty / Pool
    draw_arrow(36, 63, 20, 63)
    draw_arrow(20, 63, 20, 55, "Kitty / Pool", 'left')
    draw_box(20, 51.5, 30, 7.0, "4A. COMMON KITTY POOL", 
             "Deduct expense from central fund\nTrack member remaining equity stakes\nDeficit & low-balance alerts", C_KITTY)

    # Branch Right: Individual
    draw_arrow(64, 63, 80, 63)
    draw_arrow(80, 63, 80, 55, "Individual", 'right')
    draw_box(80, 51.5, 30, 7.0, "4B. P2P BALANCE ENGINE", 
             "Compute raw net balances:\nB_i = Paid_i - Owed_i + Settled_i\nConserves sum(B_i) == 0.00", C_P2P)

    # Family Rollup Node
    draw_arrow(80, 48.0, 80, 42.0)
    draw_box(80, 38.5, 32, 7.0, "5. FAMILY & DEPENDENT ROLLUP", 
             "Traverse sponsor_id hierarchy\nChild debt folded onto parent sponsor\nChild balance set to exact ₹0.00", C_FAMILY)

    # Debt Minimizer Node
    draw_arrow(80, 35.0, 50, 30.5)
    draw_box(50, 27.0, 52, 6.5, "6. GREEDY DEBT MINIMIZATION ALGORITHM", 
             "Partition into Debtors (B < 0) & Creditors (B > 0) -> Sort Descending\nGreedy Bipartite Min-Cash-Flow Pairing -> At most N-1 transactions", C_DEBT)

    # Settlement Node
    draw_arrow(50, 23.75, 50, 18.0)
    draw_box(50, 15.0, 46, 5.2, "7. SETTLEMENT EXECUTION & ZERO BALANCE", 
             "Log payments (Cash / UPI) -> Live Balances update to ₹0.00", C_SETTLE, text_color='#FFFFFF', sub_color='#E0F2FE')

    # Legend / Key Guarantees Box on the left
    leg_shadow = FancyBboxPatch((4.35, 23.65), 23, 17, boxstyle="round,pad=0.5",
                                facecolor='#CBD5E1', edgecolor='none', zorder=2)
    ax.add_patch(leg_shadow)
    leg_box = FancyBboxPatch((4, 24), 23, 17, boxstyle="round,pad=0.5",
                             facecolor='#F8FAFC', edgecolor='#94A3B8', linewidth=1.0, zorder=3)
    ax.add_patch(leg_box)
    ax.text(15.5, 38.5, "KEY GUARANTEES", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#0F172A', zorder=4)
    ax.text(6, 35, "• Zero Penny Drift (sum = bill)", fontsize=7.5, color='#334155', zorder=4)
    ax.text(6, 32, "• Max N-1 Transactions", fontsize=7.5, color='#334155', zorder=4)
    ax.text(6, 29, "• Children Owe 0.00 Directly", fontsize=7.5, color='#334155', zorder=4)
    ax.text(6, 26, "• Pool Equity Conservation", fontsize=7.5, color='#334155', zorder=4)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Refined vertical workflow flowchart generated at: {output_path}")

def generate_algorithm_flowchart(output_path):
    fig, ax = plt.subplots(figsize=(8.5, 5.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')

    def draw_step(x, y, w, h, num, title, subtitle, color):
        sh = FancyBboxPatch((x - w/2 + 0.3, y - h/2 - 0.3), w, h, boxstyle="round,pad=0.4,rounding_size=0.9",
                            facecolor='#CBD5E1', edgecolor='none', zorder=2)
        ax.add_patch(sh)
        box = FancyBboxPatch((x - w/2, y - h/2), w, h, boxstyle="round,pad=0.4,rounding_size=0.9",
                             facecolor='#FFFFFF', edgecolor=color, linewidth=1.3, zorder=3)
        ax.add_patch(box)

        badge = FancyBboxPatch((x - w/2, y - h/2), 6.0, h, boxstyle="round,pad=0.0,rounding_size=0.9",
                               facecolor=color, edgecolor='none', zorder=4)
        ax.add_patch(badge)
        ax.text(x - w/2 + 3.0, y, str(num), ha='center', va='center', fontsize=10.5, fontweight='bold', color='#FFFFFF', zorder=5)

        ax.text(x - w/2 + 8.0, y + 1.4, title, fontsize=9.2, fontweight='bold', color='#0F172A', va='center', zorder=5)
        ax.text(x - w/2 + 8.0, y - 1.6, subtitle, fontsize=8.0, color='#475569', va='center', zorder=5)

    def draw_down_arrow(x, y1, y2):
        arr = FancyArrowPatch((x, y1), (x, y2), arrowstyle="-|>,head_length=3.5,head_width=2.2",
                              color='#64748B', linewidth=1.2, zorder=2)
        ax.add_patch(arr)

    # Title
    ax.text(50, 96, "Greedy Bipartite Debt Minimization Algorithm", ha='center', va='center',
            fontsize=12, fontweight='bold', color='#1E3A8A')
    ax.text(50, 92, "Compresses mutual cross-debts into at most N - 1 direct payments",
            ha='center', va='center', fontsize=8.2, fontstyle='italic', color='#64748B')

    draw_step(50, 81.5, 75, 7.0, "1", "Compute Net Balances", "B_i = Total Paid_i - Total Owed_i", '#2563EB')
    draw_down_arrow(50, 78.0, 71.5)

    draw_step(50, 68.0, 75, 7.0, "2", "Partition Members", "Debtors (B_i < -0.01) and Creditors (B_j > 0.01)", '#7C3AED')
    draw_down_arrow(50, 64.5, 58.0)

    draw_step(50, 54.5, 75, 7.0, "3", "Sort Descending by Amount", "Prioritizes matching largest debtor with largest creditor", '#D97706')
    draw_down_arrow(50, 51.0, 44.5)

    draw_step(50, 41.0, 75, 7.0, "4", "Greedy Bilateral Settle", "Transfer T = min(debt, credit); advance zeroed pointer", '#059669')
    draw_down_arrow(50, 37.5, 31.0)

    draw_step(50, 27.5, 75, 7.0, "5", "Termination Guarantee", "All balances become 0.00 in at most N - 1 payments", '#0F766E')

    # Example summary box at bottom
    ex = FancyBboxPatch((12.5, 4), 75, 14, boxstyle="round,pad=0.4,rounding_size=0.8",
                        facecolor='#F8FAFC', edgecolor='#CBD5E1', linewidth=1.0, zorder=3)
    ax.add_patch(ex)
    ax.text(50, 14.5, "Worked Example (4 Members):", ha='center', va='center',
            fontsize=8.5, fontweight='bold', color='#1E293B')
    ax.text(50, 9.5, "Alice (-₹60), Bob (-₹40)  vs  Charlie (+₹70), David (+₹30)\n"
                     "1. Alice pays Charlie ₹60  |  2. Bob pays Charlie ₹10  |  3. Bob pays David ₹30\n"
                     "Result: Completely settled in 3 payments (reduced from 6 naive debts)",
            ha='center', va='center', fontsize=7.8, color='#475569', linespacing=1.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Algorithm flowchart generated at: {output_path}")

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_wf = os.path.join(base_dir, "scripts", "flowchart.png")
    out_algo = os.path.join(base_dir, "scripts", "debt_minimization_flowchart.png")
    generate_vertical_workflow_flowchart(out_wf)
    generate_algorithm_flowchart(out_algo)
