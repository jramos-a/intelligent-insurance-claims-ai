"""initial schema"""
import sqlalchemy as sa
from alembic import op
revision, down_revision = "0001", None
def upgrade():
    op.create_table("claims", sa.Column("id", sa.String, primary_key=True), sa.Column("status", sa.String), sa.Column("owner", sa.String), sa.Column("assignee", sa.String), sa.Column("created", sa.String), sa.Column("data", sa.JSON))
    for c in ("status", "owner", "assignee"): op.create_index(f"ix_claims_{c}", "claims", [c])
    op.create_table("audit_log", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("ts", sa.String), sa.Column("claim_id", sa.String), sa.Column("actor", sa.String), sa.Column("action", sa.String), sa.Column("detail", sa.JSON))
    op.create_index("ix_audit_log_claim_id", "audit_log", ["claim_id"])
def downgrade(): op.drop_table("audit_log"); op.drop_table("claims")
