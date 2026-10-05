/**
 * Task interaction handler with optimistic UI updates and rollback
 */

document.addEventListener("DOMContentLoaded", () => {
    const listContainer = document.getElementById("task-list-container");
    if (!listContainer) return;

    listContainer.addEventListener("click", async (e) => {
        const reopenBtn = e.target.closest(".btn-reopen-task");
        if (reopenBtn) {
            e.preventDefault();
            const taskId = reopenBtn.dataset.taskId;
            const badge = document.getElementById(`task-badge-${taskId}`);
            const actionsContainer = reopenBtn.closest(".task-actions");

            if (!taskId || !badge || !actionsContainer) return;

            // 1. Save previous state for rollback
            const prevStatusText = badge.textContent;
            const prevBadgeClass = badge.className;
            const prevActionsHTML = actionsContainer.innerHTML;

            // 2. Optimistic UI update
            badge.textContent = "pendiente";
            badge.className = "badge badge-pendiente";
            reopenBtn.disabled = true;
            reopenBtn.textContent = "Reabriendo...";

            // 3. Send API request
            const result = await API.post(`/api/tasks/${taskId}/reopen`);

            if (!result.success) {
                // 4. Rollback on failure
                badge.textContent = prevStatusText;
                badge.className = prevBadgeClass;
                actionsContainer.innerHTML = prevActionsHTML;
                showNotification(`Error al reabrir tarea: ${result.error}`, "error");
                return;
            }

            // 5. Update actions container upon success
            const deleteFormHTML = `
                <form method="POST" action="/tasks/${taskId}/delete" class="delete-task-form inline-form">
                    <button type="submit" class="btn btn-sm btn-danger btn-delete-task">
                        Eliminar
                    </button>
                </form>
            `;
            actionsContainer.innerHTML = `
                <button type="button" class="btn btn-sm btn-primary btn-advance-status" 
                        data-task-id="${taskId}" data-next-status="en_progreso">
                    Iniciar ▶
                </button>
                <a href="/tasks/${taskId}/edit" class="btn btn-sm btn-outline">Editar</a>
                ${deleteFormHTML}
            `;
            showNotification("Tarea reabierta exitosamente.", "success");
            return;
        }

        const btn = e.target.closest(".btn-advance-status");
        if (!btn) return;

        const taskId = btn.dataset.taskId;
        const nextStatus = btn.dataset.nextStatus;
        const badge = document.getElementById(`task-badge-${taskId}`);
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
        const deleteFormHTML = `
            <form method="POST" action="/tasks/${taskId}/delete" class="delete-task-form inline-form">
                <button type="submit" class="btn btn-sm btn-danger btn-delete-task">
                    Eliminar
                </button>
            </form>
        `;

        if (nextStatus === "en_progreso") {
            actionsContainer.innerHTML = `
                <button type="button" class="btn btn-sm btn-success btn-advance-status" 
                        data-task-id="${taskId}" data-next-status="completada">
                    Completar ✓
                </button>
                <a href="/tasks/${taskId}/edit" class="btn btn-sm btn-outline">Editar</a>
                ${deleteFormHTML}
            `;
            showNotification("Tarea marcada como 'en progreso'", "success");
        } else if (nextStatus === "completada") {
            const reopenFormHTML = `
                <form method="POST" action="/tasks/${taskId}/reopen" class="reopen-task-form inline-form">
                    <button type="submit" class="btn btn-sm btn-secondary btn-reopen-task" data-task-id="${taskId}">
                        Reabrir ↺
                    </button>
                </form>
            `;
            actionsContainer.innerHTML = `
                ${reopenFormHTML}
                <a href="/tasks/${taskId}/edit" class="btn btn-sm btn-outline">Editar</a>
                ${deleteFormHTML}
            `;
            showNotification("¡Tarea completada con éxito!", "success");
        }
    });

    // Wire native browser confirmation for task deletion
    listContainer.addEventListener("submit", (e) => {
        const deleteForm = e.target.closest(".delete-task-form");
        if (deleteForm) {
            if (!confirm("¿Está seguro de que desea eliminar esta tarea?")) {
                e.preventDefault();
            }
        }
    });
});
