"""005_task_ordering

Revision ID: 6e525f39f386
Revises: 4cee1aa5ad3f
Create Date: 2026-10-06 13:09:31.366264

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e525f39f386'
down_revision = '4cee1aa5ad3f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=True))

    # Deterministic position initialization
    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id FROM users")).fetchall()
    for row in users:
        user_id = row[0]
        tasks = connection.execute(sa.text(
            "SELECT id FROM tasks WHERE user_id = :uid ORDER BY created_at ASC, id ASC"
        ), {"uid": user_id}).fetchall()
        
        for idx, task_row in enumerate(tasks):
            connection.execute(sa.text(
                "UPDATE tasks SET position = :pos WHERE id = :tid"
            ), {"pos": (idx + 1) * 10, "tid": task_row[0]})

    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_chk_names = {c['name'] for c in insp.get_check_constraints('audit_logs') if c.get('name')}

    with op.batch_alter_table('audit_logs', recreate='always', schema=None) as batch_op:
        if 'chk_audit_logs_action' in existing_chk_names:
            batch_op.drop_constraint('chk_audit_logs_action', type_='check')
        batch_op.create_check_constraint(
            'chk_audit_logs_action',
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change', 'assign', 'reassign', 'unassign', 'reorder')"
        )

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_chk_names = {c['name'] for c in insp.get_check_constraints('audit_logs') if c.get('name')}

    with op.batch_alter_table('audit_logs', recreate='always', schema=None) as batch_op:
        if 'chk_audit_logs_action' in existing_chk_names:
            batch_op.drop_constraint('chk_audit_logs_action', type_='check')
        batch_op.create_check_constraint(
            'chk_audit_logs_action',
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change', 'assign', 'reassign', 'unassign')"
        )

    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('position')
