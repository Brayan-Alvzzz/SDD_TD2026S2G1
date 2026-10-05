import pytest
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError, NotFoundError


def test_create_category_success(user_service, category_service):
    """User can create a category with a valid name, and whitespace is trimmed."""
    user = user_service.register_user("cat_user1@example.com", "password123")
    cat = category_service.create_category(user.id, "  Trabajo y Oficina  ")

    assert cat.id is not None
    assert cat.user_id == user.id
    assert cat.name == "Trabajo y Oficina"
    assert cat.created_at != ""


def test_create_category_validation_errors(user_service, category_service):
    """Category name cannot be empty, whitespace-only, or exceed 50 characters."""
    user = user_service.register_user("cat_user2@example.com", "password123")

    with pytest.raises(ValidationError, match="obligatorio"):
        category_service.create_category(user.id, "")

    with pytest.raises(ValidationError, match="obligatorio"):
        category_service.create_category(user.id, "   ")

    with pytest.raises(ValidationError, match="50 caracteres"):
        category_service.create_category(user.id, "x" * 51)


def test_create_category_duplicate_same_user_rejected(user_service, category_service):
    """A user cannot create two categories with the same name."""
    user = user_service.register_user("cat_user3@example.com", "password123")
    category_service.create_category(user.id, "Proyectos")

    with pytest.raises((ConflictError, ValidationError), match=r"(?i)(ya existe|ya posee)"):
        category_service.create_category(user.id, "Proyectos")

    with pytest.raises((ConflictError, ValidationError), match=r"(?i)(ya existe|ya posee)"):
        category_service.create_category(user.id, "  Proyectos  ")


def test_create_category_multi_user_isolation(user_service, category_service):
    """Two different users can independently create categories with the exact same name."""
    user_a = user_service.register_user("cat_usera@example.com", "password123")
    user_b = user_service.register_user("cat_userb@example.com", "password123")

    cat_a = category_service.create_category(user_a.id, "Finanzas")
    cat_b = category_service.create_category(user_b.id, "Finanzas")

    assert cat_a.id != cat_b.id
    assert cat_a.user_id == user_a.id
    assert cat_b.user_id == user_b.id
    assert cat_a.name == "Finanzas"
    assert cat_b.name == "Finanzas"


def test_list_categories_with_active_task_count(user_service, category_service, task_service):
    """list_categories returns categories belonging exclusively to the user with active task counts."""
    user_a = user_service.register_user("cat_user_list_a@example.com", "password123")
    user_b = user_service.register_user("cat_user_list_b@example.com", "password123")

    cat_trabajo = category_service.create_category(user_a.id, "Trabajo")
    cat_personal = category_service.create_category(user_a.id, "Personal")
    cat_alien = category_service.create_category(user_b.id, "AlienCat")

    # Tasks for User A: 2 active in Trabajo, 1 active in Personal, 1 soft-deleted in Trabajo
    t1 = task_service.create_task(user_a.id, "T1", category_id=cat_trabajo.id)
    t2 = task_service.create_task(user_a.id, "T2", category_id=cat_trabajo.id)
    t3 = task_service.create_task(user_a.id, "T3", category_id=cat_trabajo.id)
    task_service.delete_task(t3.id, user_a.id)  # soft deleted -> must not count

    t4 = task_service.create_task(user_a.id, "T4", category_id=cat_personal.id)
    # Task without category
    task_service.create_task(user_a.id, "T5 sin cat")

    # Task for User B in alien category
    task_service.create_task(user_b.id, "T_alien", category_id=cat_alien.id)

    cats_a = category_service.list_categories(user_a.id)
    assert len(cats_a) == 2
    cat_map = {c.name: c.task_count for c in cats_a}
    assert cat_map["Trabajo"] == 2
    assert cat_map["Personal"] == 1
    assert "AlienCat" not in cat_map


def test_delete_category_unlinks_tasks_without_deleting_them_or_losing_audit(
    user_service, category_service, task_service, task_repo, audit_repo
):
    """Deleting a category sets associated tasks' category_id to NULL via ON DELETE SET NULL, keeping tasks and audit logs intact."""
    user = user_service.register_user("cat_del_user@example.com", "password123")
    cat = category_service.create_category(user.id, "Proyecto Temporal")

    task = task_service.create_task(user.id, "Tarea Importante", category_id=cat.id)
    assert task.category_id == cat.id

    # Add audit log event
    task_service.update_task_status(task.id, user.id, "en_progreso")
    logs_before = audit_repo.list_by_task(task.id)
    assert len(logs_before) >= 2  # create + status_change

    # Delete category
    result = category_service.delete_category(cat.id, user.id)
    assert result is True

    # 1. Category is deleted
    assert category_service.category_repo.get_by_id(cat.id) is None

    # 2. Task still exists in database and is active (NOT deleted)
    persisted_task = task_repo.get_by_id(task.id)
    assert persisted_task is not None
    assert persisted_task.is_deleted is False
    assert persisted_task.status == "en_progreso"

    # 3. Task has category_id unlinked (None)
    assert persisted_task.category_id is None

    # 4. Audit logs are preserved
    logs_after = audit_repo.list_by_task(task.id)
    assert len(logs_after) == len(logs_before)


def test_delete_category_unauthorized_and_nonexistent(user_service, category_service):
    """Users cannot delete categories belonging to others or non-existent categories."""
    owner = user_service.register_user("cat_owner@example.com", "password123")
    attacker = user_service.register_user("cat_attacker@example.com", "password123")

    cat = category_service.create_category(owner.id, "Confidencial")

    # Attacker tries to delete owner's category
    with pytest.raises((UnauthorizedError, NotFoundError)):
        category_service.delete_category(cat.id, attacker.id)

    # Category must still exist
    assert category_service.category_repo.get_by_id(cat.id) is not None

    # Non-existent category
    with pytest.raises(NotFoundError):
        category_service.delete_category(99999, owner.id)
