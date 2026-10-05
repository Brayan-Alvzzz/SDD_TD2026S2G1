"""003_task_organization

Revision ID: a6aa1e24bf8e
Revises: 3acae1929949
Create Date: 2026-10-04 22:27:10.028273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6aa1e24bf8e'
down_revision = '3acae1929949'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.String(length=35), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_categories_user_name')
    )
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.create_index('idx_categories_user_id', ['user_id'], unique=False)

    # 2. Alter tasks table in batch mode with check constraints
    with op.batch_alter_table(
        'tasks',
        schema=None,
        table_args=(
            sa.CheckConstraint("status IN ('pendiente', 'en_progreso', 'completada')", name='chk_tasks_status'),
            sa.CheckConstraint("priority IN ('alta', 'media', 'baja')", name='chk_tasks_priority'),
        )
    ) as batch_op:
        batch_op.add_column(sa.Column('priority', sa.String(length=10), server_default='media', nullable=False))
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.create_index('idx_tasks_user_priority', ['user_id', 'priority'], unique=False)
        batch_op.create_index('idx_tasks_user_category', ['user_id', 'category_id'], unique=False)
        batch_op.create_foreign_key('fk_tasks_category_id_categories', 'categories', ['category_id'], ['id'], ondelete='SET NULL')

    # 3. Recreate audit_logs table to expand chk_audit_logs_action check constraint
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_chk_names = {c['name'] for c in insp.get_check_constraints('audit_logs') if c.get('name')}

    with op.batch_alter_table('audit_logs', recreate='always', schema=None) as batch_op:
        if 'chk_audit_logs_action' in existing_chk_names:
            batch_op.drop_constraint('chk_audit_logs_action', type_='check')
        batch_op.create_check_constraint(
            'chk_audit_logs_action',
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change')"
        )


def downgrade():
    # 1. Revert audit_logs check constraint
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_chk_names = {c['name'] for c in insp.get_check_constraints('audit_logs') if c.get('name')}

    with op.batch_alter_table('audit_logs', recreate='always', schema=None) as batch_op:
        if 'chk_audit_logs_action' in existing_chk_names:
            batch_op.drop_constraint('chk_audit_logs_action', type_='check')
        batch_op.create_check_constraint(
            'chk_audit_logs_action',
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen')"
        )

    # 2. Revert tasks additions
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_category_id_categories', type_='foreignkey')
        batch_op.drop_index('idx_tasks_user_category')
        batch_op.drop_index('idx_tasks_user_priority')
        batch_op.drop_column('category_id')
        batch_op.drop_column('priority')

    # 3. Drop categories table
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_index('idx_categories_user_id')

    op.drop_table('categories')
