/**
 * SplitSmart Natural Language Expense Modal Controller
 * Calls /api/groups/<group_id>/ai/parse-nl to extract expense details using Gemini AI
 * and loads the parsed output directly into the "Add Expense" form modal for user review and confirmation.
 */

async function handleNLParse() {
    const promptInput = document.getElementById('aiExpensePrompt') || document.getElementById('nlPromptInput');
    const spinner = document.getElementById('aiParseSpinner') || document.getElementById('nlSpinner');
    const btn = document.getElementById('btnExtractAI') || document.getElementById('btnNLExtract');

    if (!promptInput) return;
    const text = promptInput.value.trim();
    if (!text) {
        alert('Please enter an expense description first.');
        return;
    }

    const groupId = (typeof GROUP_ID !== 'undefined' && GROUP_ID) ? GROUP_ID : null;
    if (!groupId) {
        alert('Group ID not found.');
        return;
    }

    if (spinner) spinner.style.display = 'block';
    if (btn) btn.disabled = true;

    try {
        const res = await fetch(`/api/groups/${groupId}/ai/parse-nl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        const data = await res.json();

        if (data.success && data.parsed) {
            const p = data.parsed;

            const descInput = document.getElementById('expenseDesc');
            const amtInput = document.getElementById('expenseAmount');
            const payerSelect = document.getElementById('expensePayer');

            if (descInput) descInput.value = p.description || text;
            if (amtInput && p.amount) amtInput.value = p.amount;
            if (payerSelect && p.payer_id) payerSelect.value = p.payer_id;

            if (p.split_member_ids && p.split_member_ids.length > 0) {
                document.querySelectorAll('.participant-chk').forEach(chk => {
                    chk.checked = p.split_member_ids.includes(parseInt(chk.value));
                });
            }

            const manualTabBtn = document.getElementById('manual-tab');
            if (manualTabBtn && typeof bootstrap !== 'undefined') {
                bootstrap.Tab.getOrCreateInstance(manualTabBtn).show();
            }
        } else {
            alert(data.error || 'Failed to extract expense details.');
        }
    } catch (err) {
        alert('AI communication error: ' + err.message);
    } finally {
        if (spinner) spinner.style.display = 'none';
        if (btn) btn.disabled = false;
    }
}

// Alias for dashboard compatibility
if (typeof window !== 'undefined' && !window.triggerAITextParse) {
    window.triggerAITextParse = handleNLParse;
}
