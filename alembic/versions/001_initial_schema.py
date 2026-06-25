"""Initial schema: cameras and anpr_events tables.

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cameras ──────────────────────────────────────────────────────────────
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rtsp_url", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── anpr_events ───────────────────────────────────────────────────────────
    op.create_table(
        "anpr_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plate_number", sa.String(length=20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("camera_name", sa.String(length=100), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("raw_plate_text", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_anpr_events_plate_number", "anpr_events", ["plate_number"])
    op.create_index("ix_anpr_events_timestamp", "anpr_events", ["timestamp"])
    op.create_index("ix_anpr_events_camera_name", "anpr_events", ["camera_name"])
    op.create_index(
        "ix_anpr_events_plate_timestamp",
        "anpr_events",
        ["plate_number", "timestamp"],
    )
    op.create_index(
        "ix_anpr_events_camera_timestamp",
        "anpr_events",
        ["camera_name", "timestamp"],
    )


def downgrade() -> None:
    op.drop_table("anpr_events")
    op.drop_table("cameras")
