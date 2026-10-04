/**
 * Task interaction handler with optimistic UI updates and rollback
 */

document.addEventListener("DOMContentLoaded", () => {
    const listContainer = document.getElementById("task-list-container");
    if (!listContainer) return;

    listContainer.addEventListener("click", async (e) => {
        const btn = e.target.closest(".btn-advance-status");
        if (!btn) return;

        const taskId = btn.dataset.taskId;
        const nextStatus = btn.dataset.nextStatus;
        const badge = document.getElementById(`task-badge-{{ task.id }}`.replace("{{ task.id }}", taskId));
        const actionsContainer = btn.parentElement;

        if (!taskId || !nextStatus || !badge) return;

        // 1. Save previous state for rollback
        const prevStatusText = badge.textContent;
        const prevBadgeClass = badge.className;
        const prevActionsHTML = actionsContainer.innerHTML;

        // 2. Optimistic UI update
        badge.textContent = nextStatus.replace("_", " ");
        badge.className = `badge badge-${nextStatus}`;
        btn.disabled = true;
        btn.textContent = "Actualizando...";

        // 3. Send API request
        const result = await API.patch(`/api/tasks/${taskId}/status`, { status: nextStatus });

        if (!result.success) {
            // 4. ROLLBACK ON FAILURE
            badge.textContent = prevStatusText;
            badge.className = prevBadgeClass;
            actionsContainer.innerHTML = prevActionsHTML;
            showNotification(`Error al actualizar estado: ${result.error}`, "error");
            return;
        }

        // 5. Update next action button upon success
        if (nextStatus === "en_progreso") {
            actionsContainer.innerHTML = `
                <button type="button" class="btn btn-sm btn-success btn-advance-status" 
                        data-task-id="${taskId}" data-next-status="completada">
                    Completar ✓
                </button>
                <a href="/tasks/${taskId}/edit" class="btn btn-sm btn-outline">Editar</a>
            `;
            showNotification("Tarea marcada como 'en progreso'", "success");
        } else if (nextStatus === "completada") {
            actionsContainer.innerHTML = `
                <a href="/tasks/${taskId}/edit" class="btn btn-sm btn-outline">Editar</a>
            `;
            showNotification("¡Tarea completada con éxito!", "success");
        }
    });
});
