/**
 * TaskControl API Client
 * Enforces JSON contracts, error parsing, and facilitates optimistic UI rollbacks.
 */

const API = {
    async patch(url, data) {
        try {
            const response = await fetch(url, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await response.json().catch(() => ({
                status: "error",
                error: "Respuesta inválida del servidor"
            }));

            const isSuccess = response.ok && (result.success === true || result.status === "success");
            if (!isSuccess) {
                const errorMsg = result.error || `Error ${response.status}: Operación fallida`;
                return { success: false, error: errorMsg, status: response.status };
            }

            return { success: true, data: result.data };
        } catch (err) {
            return {
                success: false,
                error: "Error de conexión con el servidor. Se canceló la operación."
            };
        }
    },

    async put(url, data) {
        try {
            const response = await fetch(url, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await response.json().catch(() => ({
                success: false,
                error: "Respuesta inválida del servidor"
            }));

            if (!response.ok || !result.success) {
                const errorMsg = result.error || `Error ${response.status}: Operación fallida`;
                return { success: false, error: errorMsg, status: response.status };
            }

            return { success: true, data: result.data };
        } catch (err) {
            return {
                success: false,
                error: "Error de conexión con el servidor. Se canceló la operación."
            };
        }
    },

    async post(url, data = {}) {
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await response.json().catch(() => ({
                status: "error",
                error: "Respuesta inválida del servidor"
            }));

            if (!response.ok || result.status === "error" || result.success === false) {
                const errorMsg = result.message || result.error || `Error ${response.status}: Operación fallida`;
                return { success: false, error: errorMsg, status: response.status };
            }

            return { success: true, data: result.data, message: result.message };
        } catch (err) {
            return {
                success: false,
                error: "Error de conexión con el servidor. Se canceló la operación."
            };
        }
    }
};

function showNotification(message, type = "error") {
    const container = document.getElementById("flash-container");
    if (!container) return;

    const alert = document.createElement("div");
    alert.className = `alert alert-${type}`;
    
    const span = document.createElement("span");
    span.textContent = message;
    
    const closeBtn = document.createElement("button");
    closeBtn.className = "alert-close";
    closeBtn.textContent = "×";
    closeBtn.onclick = () => alert.remove();
    
    alert.appendChild(span);
    alert.appendChild(closeBtn);
    
    container.appendChild(alert);

    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}
