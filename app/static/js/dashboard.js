/**
 * SplitSmart Dashboard Client Controller (dashboard.js)
 * Implements inline 1-click settlement directly from the Settlement Plan
 * and dashboard interaction helpers.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Determine active group ID from global variable or pathname
    const getGroupId = () => {
        if (typeof GROUP_ID !== 'undefined' && GROUP_ID) return GROUP_ID;
        const parts = window.location.pathname.split('/');
        const grpIdx = parts.indexOf('groups');
        if (grpIdx !== -1 && parts[grpIdx + 1]) {
            return parseInt(parts[grpIdx + 1]);
        }
        return null;
    };

    // Attach delegated click listener for all 1-click settlement buttons
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.mark-paid-btn');
        if (!btn) return;

        e.preventDefault();

        const payerId = parseInt(btn.getAttribute('data-payer-id'));
        const payeeId = parseInt(btn.getAttribute('data-payee-id'));
        const amount = parseFloat(btn.getAttribute('data-amount'));
        const groupId = getGroupId();

        if (!groupId || isNaN(payerId) || isNaN(payeeId) || isNaN(amount) || amount <= 0) {
            alert('Invalid settlement parameters.');
            return;
        }

        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Settling...';

        try {
            const res = await fetch(`/groups/${groupId}/settle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    payer_id: payerId,
                    payee_id: payeeId,
                    amount: amount,
                    payment_method: 'UPI',
                    payment_reference: '1-click settlement'
                })
            });

            const data = await res.json();
            if (data.success) {
                btn.className = 'btn btn-sm btn-success fw-semibold';
                btn.innerHTML = '<i class="bi bi-check2-all me-1"></i> Paid!';
                setTimeout(() => {
                    window.location.reload();
                }, 400);
            } else {
                alert(data.error || 'Failed to record settlement.');
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        } catch (err) {
            alert('Error recording settlement: ' + err.message);
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });
});

/**
 * Copies the invite link to the clipboard and gives user feedback.
 */
function copyInviteLink(btn) {
    if (!btn) return;
    const linkUrl = btn.getAttribute('data-invite-url');
    if (!linkUrl) return;

    if (!navigator.clipboard) {
        prompt('Copy invite link:', linkUrl);
        return;
    }
    navigator.clipboard.writeText(linkUrl).then(() => {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2 text-success"></i> Copied!';
        btn.classList.add('border-success');
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.classList.remove('border-success');
        }, 2000);
    }).catch(() => {
        prompt('Copy invite link:', linkUrl);
    });
}
