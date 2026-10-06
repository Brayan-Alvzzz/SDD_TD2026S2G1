from flask import Blueprint, request, jsonify, session
from src.infrastructure.database import db
from src.infrastructure.repositories import NotificationRepository
from src.domain.services import NotificationService
from src.domain.exceptions import NotFoundError, UnauthorizedError

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

def get_notification_service():
    db_session = db.session
    notif_repo = NotificationRepository(db_session)
    return NotificationService(notif_repo, session=db_session)

def _auth_required():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Acceso no autorizado"}), 401
    return None

@notification_bp.route("", methods=["GET"])
def list_notifications():
    err = _auth_required()
    if err:
        return err

    user_id = session["user_id"]
    service = get_notification_service()

    notifs = service.list_notifications(user_id)
    unread_count = service.count_unread(user_id)

    data = []
    for n in notifs:
        notif_dict = {
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "is_read": n.is_read,
            "read_at": n.read_at,
            "created_at": n.created_at,
            "available": n.available
        }
        if n.available and getattr(n, "task_id", None):
            notif_dict["task"] = {
                "id": n.task_id,
                "title": getattr(n, "task_title", None),
                "status": getattr(n, "task_status", None)
            }
        else:
            notif_dict["task"] = None
        data.append(notif_dict)

    return jsonify({
        "status": "success",
        "data": data,
        "meta": {"unread_count": unread_count}
    }), 200

@notification_bp.route("/<int:notification_id>/read", methods=["POST"])
def mark_as_read(notification_id):
    err = _auth_required()
    if err:
        return err

    user_id = session["user_id"]
    service = get_notification_service()

    try:
        service.mark_as_read(notification_id, user_id)
        return jsonify({"status": "success"}), 200
    except NotFoundError:
        return jsonify({"status": "error", "message": "Notificación no encontrada."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
