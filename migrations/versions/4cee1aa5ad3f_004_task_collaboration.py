"""task_collaboration

Revision ID: 4cee1aa5ad3f
Revises: a6aa1e24bf8e
Create Date: 2026-10-05 15:49:07.989710

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4cee1aa5ad3f'
down_revision = 'a6aa1e24bf8e'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add assignee_id to tasks table
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assignee_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tasks_assignee_id_users', 'users', ['assignee_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('idx_tasks_assignee', ['assignee_id', 'is_deleted', 'created_at'], unique=False)

    # 2. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('read_at', sa.String(length=35), nullable=True),
        sa.Column('created_at', sa.String(length=35), nullable=False),
        sa.CheckConstraint("type IN ('task_assigned')", name='chk_notifications_type'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('idx_notifications_recipient', ['recipient_id', 'is_read', 'created_at'], unique=False)
        batch_op.create_index('idx_notifications_task_recipient', ['task_id', 'recipient_id'], unique=False)

    # 3. Expand audit_logs check constraint
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


def downgrade():
    bind = op.get_bind()
    
    # Pre-flight check: block downgrade if collaboration data exists
    assigned_tasks = bind.execute(sa.text("SELECT 1 FROM tasks WHERE assignee_id IS NOT NULL LIMIT 1")).scalar()
    has_notifications = bind.execute(sa.text("SELECT 1 FROM notifications LIMIT 1")).scalar()
    has_audit_logs = bind.execute(sa.text("SELECT 1 FROM audit_logs WHERE action IN ('assign', 'reassign', 'unassign') LIMIT 1")).scalar()
    
    if assigned_tasks or has_notifications or has_audit_logs:
        raise ValueError("Downgrade destructivo bloqueado: existen datos de colaboración que se perderían.")

    # 1. Revert audit_logs check constraint
    insp = sa.inspect(bind)
    existing_chk_names = {c['name'] for c in insp.get_check_constraints('audit_logs') if c.get('name')}

    with op.batch_alter_table('audit_logs', recreate='always', schema=None) as batch_op:
        if 'chk_audit_logs_action' in existing_chk_names:
            batch_op.drop_constraint('chk_audit_logs_action', type_='check')
        batch_op.create_check_constraint(
            'chk_audit_logs_action',
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change')"
        )

    # 2. Drop notifications table
    op.drop_table('notifications')

    # 3. Revert tasks additions
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_assignee_id_users', type_='foreignkey')
        batch_op.drop_index('idx_tasks_assignee')
        batch_op.drop_column('assignee_id')
