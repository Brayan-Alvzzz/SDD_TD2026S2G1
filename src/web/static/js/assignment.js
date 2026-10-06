/**
 * Assignment modal and async assignment logic
 */
document.addEventListener("DOMContentLoaded", () => {
    // --- Modal Logic (List View) ---
    const listContainer = document.getElementById("task-list-container");
    const assignModal = document.getElementById("assign-modal");
    
    let currentTaskId = null;

    if (listContainer && assignModal) {
        const assigneeInput = document.getElementById("assignee_email_input");
        const unassignBtn = document.getElementById("btn-submit-unassign");
        const closeBtn = document.querySelector("#assign-modal .close");

        listContainer.addEventListener("click", (e) => {
            const btn = e.target.closest(".btn-open-assign-modal");
            if (!btn) return;
            
            currentTaskId = btn.dataset.taskId;
            assigneeInput.value = "";
            
            // Check if currently assigned
            const assigneeSpan = document.getElementById(`task-assignee-${currentTaskId}`);
            if (assigneeSpan && assigneeSpan.style.display !== "none" && assigneeSpan.textContent.trim() !== "") {
                unassignBtn.style.display = "inline-block";
            } else {
                unassignBtn.style.display = "none";
            }

            assignModal.style.display = "block";
        });

        const closeModal = () => {
            assignModal.style.display = "none";
            currentTaskId = null;
        };

        closeBtn.addEventListener("click", closeModal);
        window.addEventListener("click", (e) => {
            if (e.target === assignModal) {
                closeModal();
            }
        });
    }

    // --- Global Form Submission Intercept (Modal and Detail View) ---
    document.addEventListener("submit", async (e) => {
        const assignForm = e.target.closest(".assign-task-form") || e.target.closest("#assign-task-form");
        if (!assignForm) return;

        e.preventDefault();
        const taskId = assignForm.dataset.taskId || currentTaskId;
        if (!taskId) return;

        const emailInput = assignForm.querySelector("input[name='assignee_email']");
        const email = emailInput ? emailInput.value.trim() : "";
        if (!email) return;

        const submitBtn = assignForm.querySelector(".btn-submit-assign");
        const prevText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = "Asignando...";

        const result = await API.put(`/api/tasks/${taskId}/assignee`, { assignee_email: email });

        submitBtn.disabled = false;
        submitBtn.textContent = prevText;

        if (!result.success) {
            showNotification(`Error: ${result.error}`, "error");
            return;
        }

        // Update UI without reload
        const assigneeSpan = document.getElementById(`task-assignee-${taskId}`);
        if (assigneeSpan) {
            assigneeSpan.textContent = `👤 ${email}`;
            assigneeSpan.style.display = "inline-block";
        }

        const openModalBtn = document.querySelector(`.btn-open-assign-modal[data-task-id='${taskId}']`);
        if (openModalBtn) {
            openModalBtn.textContent = "Reasignar";
        }

        const unassignBtn = document.getElementById("btn-submit-unassign") || document.querySelector(`.delete-task-assignee-form[data-task-id='${taskId}'] .btn-submit-unassign`);
        if (unassignBtn && assignModal) {
            unassignBtn.style.display = "inline-block";
        } else if (unassignBtn && !assignModal) {
            const deleteForm = unassignBtn.closest(".delete-task-assignee-form");
            if (deleteForm) deleteForm.style.display = "inline-block";
            const assignContainer = document.getElementById(`task-assignee-container-${taskId}`);
            if (assignContainer) {
                assignContainer.style.display = "block";
                const span = document.getElementById(`task-assignee-${taskId}`);
                if (span) span.textContent = email;
            }
            const label = assignForm.querySelector("label");
            if (label) label.textContent = "Reasignar a:";
        }

        showNotification("Tarea asignada correctamente", "success");
        if (assignModal) assignModal.style.display = "none";
    });

    document.addEventListener("click", async (e) => {
        const unassignBtn = e.target.closest("#btn-submit-unassign") || e.target.closest(".btn-submit-unassign");
        if (!unassignBtn) return;

        if (unassignBtn.type === "submit") e.preventDefault();

        const form = unassignBtn.closest(".delete-task-assignee-form");
        const taskId = (form && form.dataset.taskId) ? form.dataset.taskId : currentTaskId;
        if (!taskId) return;

        if (form && !confirm("¿Remover asignación?")) {
            return;
        }

        const prevText = unassignBtn.textContent;
        unassignBtn.disabled = true;
        unassignBtn.textContent = "Desasignando...";

        const result = await API.delete(`/api/tasks/${taskId}/assignee`);

        unassignBtn.disabled = false;
        unassignBtn.textContent = prevText;

        if (!result.success) {
            showNotification(`Error: ${result.error}`, "error");
            return;
        }

        // Update UI without reload
        const assigneeSpan = document.getElementById(`task-assignee-${taskId}`);
        if (assigneeSpan) {
            assigneeSpan.textContent = "";
            assigneeSpan.style.display = "none";
        }

        const openModalBtn = document.querySelector(`.btn-open-assign-modal[data-task-id='${taskId}']`);
        if (openModalBtn) {
            openModalBtn.textContent = "Asignar";
        }

        if (unassignBtn.id === "btn-submit-unassign") {
            unassignBtn.style.display = "none";
        } else {
            // detail view
            const deleteForm = unassignBtn.closest(".delete-task-assignee-form");
            if (deleteForm) deleteForm.style.display = "none";
            const assignContainer = document.getElementById(`task-assignee-container-${taskId}`);
            if (assignContainer) assignContainer.style.display = "none";
            
            // Show assign form
            const assignForm = document.querySelector(`.assign-task-form[data-task-id='${taskId}']`);
            if (assignForm) {
                const label = assignForm.querySelector("label");
                if (label) label.textContent = "Asignar a:";
            }
        }

        showNotification("Asignación removida", "success");
        if (assignModal) assignModal.style.display = "none";
    });
});
