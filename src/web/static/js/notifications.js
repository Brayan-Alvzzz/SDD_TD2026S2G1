/**
 * Async notifications marking
 */
document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", async (e) => {
        const btn = e.target.closest(".btn-mark-read");
        if (!btn) return;

        const notifId = btn.dataset.notifId;
        if (!notifId) return;

        const notifCard = btn.closest(".notif-card");
        const actionsContainer = btn.parentElement;

        btn.disabled = true;
        btn.textContent = "Marcando...";

        const result = await API.post(`/api/notifications/${notifId}/read`);

        if (!result.success) {
            btn.disabled = false;
            btn.textContent = "Marcar como leída";
            showNotification(`Error: ${result.error}`, "error");
            return;
        }

        // Update UI
        if (notifCard) {
            notifCard.classList.remove("unread");
            const message = notifCard.querySelector(".notif-message");
            if (message) message.classList.remove("unread");
        }

        // Replace button with "✓ Leída"
        actionsContainer.innerHTML = `<span style="font-size: 0.75rem; color: var(--text-muted);">✓ Leída</span>`;

        // Decrease unread counter by 1
        const counter = document.getElementById("unread-counter");
        if (counter) {
            let count = parseInt(counter.textContent, 10);
            if (!isNaN(count) && count > 0) {
                count -= 1;
                if (count === 0) {
                    counter.style.display = "none";
                } else {
                    counter.textContent = count;
                }
            }
        }
    });
});
