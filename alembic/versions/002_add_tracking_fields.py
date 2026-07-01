"""Add track_id, vehicle_type, best_plate_path to anpr_events.

Revision ID: 002
Revises: 001
Create Date: 2026-06-29 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("anpr_events", sa.Column("track_id", sa.Integer(), nullable=True))
    op.add_column("anpr_events", sa.Column("vehicle_type", sa.String(length=20), nullable=True))
    op.add_column("anpr_events", sa.Column("best_plate_path", sa.Text(), nullable=True))

    op.create_index("ix_anpr_events_track_id", "anpr_events", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_anpr_events_track_id", table_name="anpr_events")
    op.drop_column("anpr_events", "best_plate_path")
    op.drop_column("anpr_events", "vehicle_type")
    op.drop_column("anpr_events", "track_id")
