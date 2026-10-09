"""initial

Revision ID: 001
Revises: None
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('issue_number', sa.Integer(), nullable=True),
        sa.Column('repo_full_name', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('base_commit_sha', sa.Text(), nullable=True),
    )
    # Index on repo_full_name
    op.create_index('ix_tasks_repo_full_name', 'tasks', ['repo_full_name'])

    # 2. Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('iteration', sa.Integer(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('model', sa.Text(), nullable=True),
        sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Index on task_id
    op.create_index('ix_agent_runs_task_id', 'agent_runs', ['task_id'])

    # 3. Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artifact_type', sa.Text(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Index on task_id
    op.create_index('ix_artifacts_task_id', 'artifacts', ['task_id'])

    # 4. Create pull_requests table
    op.create_table(
        'pull_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=True),
        sa.Column('branch_name', sa.Text(), nullable=True),
        sa.Column('ci_status', sa.Text(), nullable=True),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rolled_back_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Index on task_id
    op.create_index('ix_pull_requests_task_id', 'pull_requests', ['task_id'])

    # 5. Create rollback_events table
    op.create_table(
        'rollback_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('snapshot_sha', sa.Text(), nullable=True),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Index on task_id
    op.create_index('ix_rollback_events_task_id', 'rollback_events', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_rollback_events_task_id', table_name='rollback_events')
    op.drop_table('rollback_events')
    
    op.drop_index('ix_pull_requests_task_id', table_name='pull_requests')
    op.drop_table('pull_requests')
    
    op.drop_index('ix_artifacts_task_id', table_name='artifacts')
    op.drop_table('artifacts')
    
    op.drop_index('ix_agent_runs_task_id', table_name='agent_runs')
    op.drop_table('agent_runs')
    
    op.drop_index('ix_tasks_repo_full_name', table_name='tasks')
    op.drop_table('tasks')
