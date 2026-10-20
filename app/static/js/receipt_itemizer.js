/**
 * SplitSmart Smart Receipt Itemizer & Dish Assignment Controller
 * Calls /api/groups/<group_id>/ai/parse-receipt using Gemini Vision OCR
 * Renders interactive dish-assignment chips, live proportional tax/tip recalculation,
 * and records itemized splits to the transactional ledger.
 */

let scannedReceiptData = {
    merchant_name: '',
    items: [],
    tax: 0.0,
    tip: 0.0,
    discount: 0.0,
    total: 0.0
};

async function handleReceiptScan() {
    const fileInput = document.getElementById('modalReceiptFile');
    const spinner = document.getElementById('receiptModalSpinner');
    const btn = document.getElementById('btnReceiptScan');
    const container = document.getElementById('receiptItemizerContainer');
    const footer = document.getElementById('receiptModalFooter');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        alert('Please choose a receipt image first.');
        return;
    }

    const formData = new FormData();
    formData.append('receipt_file', fileInput.files[0]);

    if (spinner) spinner.style.display = 'block';
    if (btn) btn.disabled = true;

    try {
        const res = await fetch(`/api/groups/${GROUP_ID}/ai/parse-receipt`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success && data.receipt) {
            const r = data.receipt;
            scannedReceiptData.merchant_name = r.merchant_name || 'Restaurant Bill';
            scannedReceiptData.tax = parseFloat(r.tax || 0);
            scannedReceiptData.tip = parseFloat(r.tip || 0);
            scannedReceiptData.discount = parseFloat(r.discount || 0);
            scannedReceiptData.total = parseFloat(r.total || 0);

            // Populate inputs
            const taxInput = document.getElementById('receiptTax');
            const tipInput = document.getElementById('receiptTip');
            const discInput = document.getElementById('receiptDiscount');
            if (taxInput) taxInput.value = scannedReceiptData.tax.toFixed(2);
            if (tipInput) tipInput.value = scannedReceiptData.tip.toFixed(2);
            if (discInput) discInput.value = scannedReceiptData.discount.toFixed(2);

            // Populate items with default assignment to all members
            scannedReceiptData.items = (r.items || []).map(item => ({
                name: item.name,
                price: parseFloat(item.unit_price || item.total_price || 0),
                quantity: parseFloat(item.quantity || 1),
                assigned_members: GROUP_MEMBERS.map(m => m.id)
            }));

            renderDishItems();
            if (container) container.style.display = 'block';
            if (footer) footer.style.display = 'flex';
        } else {
            alert(data.error || 'Failed to scan receipt image.');
        }
    } catch (err) {
        alert('Receipt scanning error: ' + err.message);
    } finally {
        if (spinner) spinner.style.display = 'none';
        if (btn) btn.disabled = false;
    }
}

function renderDishItems() {
    const list = document.getElementById('dishItemsList');
    if (!list) return;
    list.innerHTML = '';

    scannedReceiptData.items.forEach((item, idx) => {
        const itemTotal = (item.price * item.quantity).toFixed(2);
        const row = document.createElement('div');
        row.className = 'p-3 bg-white border rounded shadow-sm';

        let chipsHtml = '';
        GROUP_MEMBERS.forEach(m => {
            const isAssigned = item.assigned_members.includes(m.id);
            chipsHtml += `
                <button type="button" 
                    class="badge rounded-pill me-1 mb-1 btn-dish-chip ${isAssigned ? 'bg-primary text-white border-0' : 'bg-light text-dark border'}"
                    style="cursor: pointer; font-size: 0.85rem; padding: 6px 12px;"
                    onclick="toggleDishMemberAssignment(${idx}, ${m.id})">
                    ${isAssigned ? '<i class="bi bi-check-lg me-1"></i>' : ''}${m.name}
                </button>
            `;
        });

        row.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold text-dark fs-6">${item.name} ${item.quantity > 1 ? '(' + item.quantity + 'x)' : ''}</span>
                <span class="badge bg-success-subtle text-success fs-6 border border-success-subtle">${GROUP_CURRENCY} ${itemTotal}</span>
            </div>
            <div class="d-flex flex-wrap align-items-center">
                <span class="small text-muted me-2">Who ate this?</span>
                ${chipsHtml}
            </div>
        `;
        list.appendChild(row);
    });

    updateLiveItemizerShares();
}

function toggleDishMemberAssignment(dishIdx, memberId) {
    const item = scannedReceiptData.items[dishIdx];
    if (!item) return;

    const exists = item.assigned_members.indexOf(memberId);
    if (exists > -1) {
        item.assigned_members.splice(exists, 1);
    } else {
        item.assigned_members.push(memberId);
    }

    renderDishItems();
}

function updateLiveItemizerShares() {
    const taxInput = document.getElementById('receiptTax');
    const tipInput = document.getElementById('receiptTip');
    const discInput = document.getElementById('receiptDiscount');

    const tax = taxInput ? parseFloat(taxInput.value) || 0 : 0;
    const tip = tipInput ? parseFloat(tipInput.value) || 0 : 0;
    const discount = discInput ? parseFloat(discInput.value) || 0 : 0;

    let memberSubtotals = {};
    let totalItemsSubtotal = 0;

    GROUP_MEMBERS.forEach(m => { memberSubtotals[m.id] = 0; });

    scannedReceiptData.items.forEach(item => {
        const itemTotal = item.price * item.quantity;
        totalItemsSubtotal += itemTotal;
        const numAssigned = item.assigned_members.length;
        if (numAssigned > 0) {
            const share = itemTotal / numAssigned;
            item.assigned_members.forEach(mid => {
                memberSubtotals[mid] = (memberSubtotals[mid] || 0) + share;
            });
        }
    });

    const netAdjustment = tax + tip - discount;
    const preview = document.getElementById('liveSharesPreview');
    if (!preview) return;
    preview.innerHTML = '';

    GROUP_MEMBERS.forEach(m => {
        const sub = memberSubtotals[m.id] || 0;
        let finalShare = sub;
        if (totalItemsSubtotal > 0) {
            finalShare += (sub / totalItemsSubtotal) * netAdjustment;
        }
        if (finalShare < 0) finalShare = 0;

        preview.innerHTML += `
            <div class="badge bg-white text-dark border p-2 shadow-sm">
                <strong>${m.name}:</strong> ${GROUP_CURRENCY} ${finalShare.toFixed(2)}
            </div>
        `;
    });
}

async function saveItemizedExpense() {
    const payerSelect = document.getElementById('receiptPayer');
    const taxInput = document.getElementById('receiptTax');
    const tipInput = document.getElementById('receiptTip');
    const discInput = document.getElementById('receiptDiscount');

    const payer_id = payerSelect ? parseInt(payerSelect.value) : GROUP_MEMBERS[0].id;
    const tax = taxInput ? parseFloat(taxInput.value) || 0 : 0;
    const tip = tipInput ? parseFloat(tipInput.value) || 0 : 0;
    const discount = discInput ? parseFloat(discInput.value) || 0 : 0;

    let subtotal = 0;
    scannedReceiptData.items.forEach(i => { subtotal += i.price * i.quantity; });
    const totalAmount = subtotal + tax + tip - discount;

    const payload = {
        title: scannedReceiptData.merchant_name || 'Itemized Bill',
        description: scannedReceiptData.merchant_name || 'Itemized Bill',
        amount: totalAmount,
        category: 'Food',
        split_type: 'ITEMIZED',
        payers: [{ member_id: payer_id, amount_paid: totalAmount }],
        receipt_items: scannedReceiptData.items,
        tax: tax,
        tip: tip,
        discount: discount
    };

    try {
        const res = await fetch(`/groups/${GROUP_ID}/expenses`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to save itemized expense.');
        }
    } catch (err) {
        alert('Save error: ' + err.message);
    }
}
