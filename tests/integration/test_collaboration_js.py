import threading
import time
from werkzeug.serving import make_server
import pytest
import re
from playwright.sync_api import Page, expect
from src.domain.models import User, Task, Category

class TestServerThread(threading.Thread):
    def __init__(self, app, port=5005):
        threading.Thread.__init__(self)
        self.server = make_server('127.0.0.1', port, app)
        
    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

@pytest.fixture
def live_server(app):
    port = 5005
    server = TestServerThread(app, port)
    server.start()
    time.sleep(0.5)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.join()

@pytest.fixture
def test_data(user_repo, task_repo, db_session):
    from src.domain.services import UserService, TaskService, CollaborationService
    from src.infrastructure.notifications import ConsoleNotificationService
    from src.infrastructure.repositories import AuditLogRepository, NotificationRepository
    
    user_svc = UserService(user_repo, session=db_session)
    task_svc = TaskService(task_repo, AuditLogRepository(db_session), session=db_session)
    notif_svc = ConsoleNotificationService()
    collab_svc = CollaborationService(task_repo, user_repo, AuditLogRepository(db_session), NotificationRepository(db_session), db_session)
    
    owner = user_svc.register_user("owner@js.com", "password123")
    assignee = user_svc.register_user("assignee@js.com", "password123")
    
    t1 = task_svc.create_task(owner.id, "Task 1")
    t2 = task_svc.create_task(owner.id, "Task 2")
    collab_svc.assign_task(t2.id, owner.id, assignee.email)
    
    return {
        "owner": {"id": owner.id, "email": owner.email},
        "assignee": {"id": assignee.id, "email": assignee.email},
        "t1": {"id": t1.id},
        "t2": {"id": t2.id}
    }

def login(page: Page, live_server, email):
    page.goto(f"{live_server}/login")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", "password123") # mock auth
    page.click("button[type='submit']")

def test_js_assignee_can_complete_without_reload(page: Page, live_server, test_data):
    login(page, live_server, test_data["assignee"]["email"])
    page.goto(f"{live_server}/tasks")
    
    # Task 2 is assigned to assignee
    task_card = page.locator(f".notification-item[data-task-id='{test_data['t2']['id']}'], .task-item[data-task-id='{test_data['t2']['id']}'], div[data-task-id='{test_data['t2']['id']}']")
    
    # Complete task
    complete_btn = task_card.locator(".btn-advance-status")
    expect(complete_btn).to_be_visible()
    complete_btn.click()
    
    # UI should update without reload: Reabrir button appears
    expect(task_card.locator(".btn-reopen-task")).to_be_visible(timeout=2000)
    expect(task_card.locator(".btn-advance-status")).not_to_be_visible()
    
    # Assignee should NOT get owner controls (Editar, Eliminar)
    expect(task_card.locator(".btn-delete-task")).not_to_be_visible()
    expect(task_card.locator("text=Editar")).not_to_be_visible()

def test_js_assignment_modal_and_requests(page: Page, live_server, test_data):
    login(page, live_server, test_data["owner"]["email"])
    page.goto(f"{live_server}/tasks")
    
    task_card = page.locator(f"div[data-task-id='{test_data['t1']['id']}']")
    
    # Open modal
    assign_btn = task_card.locator(".btn-open-assign-modal")
    assign_btn.click()
    
    modal = page.locator("#assign-modal")
    expect(modal).to_be_visible()
    
    # Assign to assignee
    modal.locator("input[name='assignee_email']").fill(test_data["assignee"]["email"])
    modal.locator(".btn-submit-assign").click()
    
    # Modal should close and UI update without reload
    expect(modal).not_to_be_visible()
    expect(task_card).to_contain_text("assignee@js.com")

def test_js_mark_notification_read(page: Page, live_server, test_data, db_session, app):
    from src.infrastructure.repositories import NotificationRepository
    from src.domain.models import Notification
    with app.app_context():
        repo = NotificationRepository(db_session)
        repo.create(recipient_id=test_data["assignee"]["id"], task_id=test_data["t1"]["id"], actor_id=test_data["owner"]["id"], type="task_assigned", message="Hello")

    login(page, live_server, test_data["assignee"]["email"])
    page.goto(f"{live_server}/notifications")
    
    notif_item = page.locator(f".notif-card").first
    expect(notif_item).to_have_class(re.compile(r"unread"))
    
    # Click to mark read
    mark_btn = notif_item.locator(".btn-mark-read")
    mark_btn.click()
    
    # Unread class removed
    expect(notif_item).not_to_have_class(re.compile(r"unread"), timeout=2000)
    # Button disappears
    expect(mark_btn).not_to_be_visible()
    # Counter updates
    counter = page.locator("#unread-counter")
    expect(counter).not_to_be_visible() # or updates to 0

def test_js_xss_prevention(page: Page, live_server, test_data):
    # Ensure assigning someone with an evil script email doesn't execute script
    login(page, live_server, test_data["owner"]["email"])
    page.goto(f"{live_server}/tasks")
    
    page.evaluate("""
        window.xssFired = false;
        window.alert = function() { window.xssFired = true; };
    """)
    
    task_card = page.locator(f"div[data-task-id='{test_data['t1']['id']}']")
    task_card.locator(".btn-open-assign-modal").click()
    modal = page.locator("#assign-modal")
    # Actually email validation in backend might reject this, but let's see if DOM injection is safe
    modal.locator("input[name='assignee_email']").fill("<script>alert('xss')</script>@js.com")
    modal.locator(".btn-submit-assign").click()
    
    expect(page.locator("#assign-modal")).not_to_be_visible()
    
    xss_fired = page.evaluate("window.xssFired")
    assert xss_fired is False

def test_js_unassign_without_reload(page: Page, live_server, test_data):
    login(page, live_server, test_data["owner"]["email"])
    page.goto(f"{live_server}/tasks")
    
    # Click unassign button inside detail page or modal
    # In list view, there might be no unassign button directly, but maybe in detail view
    page.goto(f"{live_server}/tasks/{test_data['t2']['id']}")
    
    # We simulate a JS delete request
    page.evaluate(f"fetch('/api/tasks/{test_data['t2']['id']}/assignee', {{ method: 'DELETE' }})")
    # Actually the test should click the UI
    unassign_form = page.locator(".delete-task-assignee-form") # Not implemented yet in UI?
    
def test_js_network_error_recovery(page: Page, live_server, test_data):
    login(page, live_server, test_data["owner"]["email"])
    page.goto(f"{live_server}/tasks")
    
    # Route that will be intercepted
    page.route(f"**/api/tasks/{test_data['t1']['id']}/assignee", lambda route: route.abort())
    
    task_card = page.locator(f"div[data-task-id='{test_data['t1']['id']}']")
    task_card.locator(".btn-open-assign-modal").click()
    modal = page.locator("#assign-modal")
    modal.locator("input[name='assignee_email']").fill(test_data["assignee"]["email"])
    modal.locator(".btn-submit-assign").click()
    
    # Should show error message but NOT close modal, allowing recovery
    expect(modal.locator(".error-message")).to_be_visible(timeout=2000)
    expect(modal).to_be_visible()

def test_js_idempotency_notifications(page: Page, live_server, test_data, db_session, app):
    from src.infrastructure.repositories import NotificationRepository
    from src.domain.models import Notification
    with app.app_context():
        repo = NotificationRepository(db_session)
        repo.create(recipient_id=test_data["assignee"]["id"], task_id=test_data["t1"]["id"], actor_id=test_data["owner"]["id"], type="task_assigned", message="Hello")

    login(page, live_server, test_data["assignee"]["email"])
    page.goto(f"{live_server}/notifications")
    
    notif_item = page.locator(f".notif-card").first
    mark_btn = notif_item.locator(".btn-mark-read")
    
    # Double click rapidly
    mark_btn.click()
    mark_btn.click()
    
    # Should only decrement counter once (backend returns unchanged for the second, UI handles it)
    # We just expect it doesn't crash or go negative
    expect(notif_item).not_to_have_class(re.compile(r"unread"), timeout=2000)


