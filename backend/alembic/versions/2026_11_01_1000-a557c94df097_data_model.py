"""data model

Revision ID: a557c94df097
Revises: 52e9b26bd4f0
Create Date: 2026-11-01 10:00:13.724225+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a557c94df097"
down_revision: str | Sequence[str] | None = "52e9b26bd4f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # citext потрібен для email без урахування регістру.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "school",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("region_code", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), server_default="Europe/Kyiv", nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school")),
    )
    op.create_index("ix_school_region_code", "school", ["region_code"], unique=False)
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role <> 'student' OR (email IS NULL AND password_hash IS NULL)",
            name=op.f("ck_app_user_student_no_credentials"),
        ),
        sa.CheckConstraint(
            "role IN ('student', 'teacher', 'parent', 'admin')", name=op.f("ck_app_user_role")
        ),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 50",
            name=op.f("ck_app_user_display_name_length"),
        ),
        sa.CheckConstraint(
            "last_name IS NULL OR char_length(last_name) BETWEEN 1 AND 50",
            name=op.f("ck_app_user_last_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["school.id"], name=op.f("fk_app_user_school_id_school")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_table(
        "school_class",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("academic_year", sa.Text(), nullable=False),
        sa.Column("join_code", sa.Text(), nullable=False),
        sa.Column("join_code_expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("grade BETWEEN 1 AND 11", name=op.f("ck_school_class_grade_range")),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.id"],
            name=op.f("fk_school_class_school_id_school"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school_class")),
        sa.UniqueConstraint("join_code", name=op.f("uq_school_class_join_code")),
        sa.UniqueConstraint(
            "school_id", "academic_year", "name", name="uq_school_class_school_year_name"
        ),
    )
    op.create_table(
        "subject",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["school.id"], name=op.f("fk_subject_school_id_school")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subject")),
    )
    op.create_table(
        "alert_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("region_code", sa.Text(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("class_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("is_drill", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("source IN ('api', 'manual')", name=op.f("ck_alert_event_source")),
        sa.ForeignKeyConstraint(
            ["class_id"], ["school_class.id"], name=op.f("fk_alert_event_class_id_school_class")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            name=op.f("fk_alert_event_created_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["school.id"], name=op.f("fk_alert_event_school_id_school")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_event")),
        sa.UniqueConstraint(
            "source", "external_id", "school_id", name="uq_alert_event_source_external_school"
        ),
    )
    op.create_index(
        "ix_alert_event_active",
        "alert_event",
        ["school_id"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "ix_alert_event_school_id_started_at",
        "alert_event",
        ["school_id", "started_at"],
        unique=False,
    )
    op.create_table(
        "class_membership",
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("member_role", sa.Text(), nullable=False),
        sa.Column(
            "joined_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "member_role IN ('student', 'teacher')", name=op.f("ck_class_membership_member_role")
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_class_membership_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_class_membership_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("class_id", "user_id", name=op.f("pk_class_membership")),
    )
    op.create_index("ix_class_membership_user_id", "class_membership", ["user_id"], unique=False)
    op.create_table(
        "knowledge_pack",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("pack_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("built_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_knowledge_pack_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_pack")),
        sa.UniqueConstraint("class_id", "pack_date", "version", name="uq_knowledge_pack_version"),
    )
    op.create_table(
        "lesson",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("shelter_part", sa.Text(), nullable=False),
        sa.Column("main_part", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'published')", name=op.f("ck_lesson_status")),
        sa.ForeignKeyConstraint(
            ["author_id"], ["app_user.id"], name=op.f("fk_lesson_author_id_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subject.id"], name=op.f("fk_lesson_subject_id_subject")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson")),
    )
    op.create_table(
        "media_asset",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("subtitles_id", sa.UUID(), nullable=True),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('video', 'image', 'subtitles')", name=op.f("ck_media_asset_kind")
        ),
        sa.ForeignKeyConstraint(
            ["subtitles_id"],
            ["media_asset.id"],
            name=op.f("fk_media_asset_subtitles_id_media_asset"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["app_user.id"], name=op.f("fk_media_asset_uploaded_by_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_asset")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_media_asset_storage_key")),
    )
    op.create_table(
        "parent_child",
        sa.Column("parent_id", sa.UUID(), nullable=False),
        sa.Column("child_id", sa.UUID(), nullable=False),
        sa.Column(
            "linked_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["child_id"],
            ["app_user.id"],
            name=op.f("fk_parent_child_child_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["app_user.id"],
            name=op.f("fk_parent_child_parent_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("parent_id", "child_id", name=op.f("pk_parent_child")),
    )
    op.create_index("ix_parent_child_child_id", "parent_child", ["child_id"], unique=False)
    op.create_table(
        "push_subscription",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("last_success_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_push_subscription_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscription")),
        sa.UniqueConstraint("endpoint", name=op.f("uq_push_subscription_endpoint")),
    )
    op.create_table(
        "schedule_slot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_schedule_slot_time_order")),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name=op.f("ck_schedule_slot_weekday_range")),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_schedule_slot_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subject.id"], name=op.f("fk_schedule_slot_subject_id_subject")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_slot")),
    )
    op.create_index(
        "ix_schedule_slot_class_id_weekday", "schedule_slot", ["class_id", "weekday"], unique=False
    )
    op.create_table(
        "sync_event",
        sa.Column("client_event_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("clock_skew_ms", sa.Integer(), nullable=True),
        sa.Column("is_suspicious", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source", sa.Text(), server_default="online", nullable=False),
        sa.Column("relayed_by", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("source IN ('online', 'qr')", name=op.f("ck_sync_event_source")),
        sa.CheckConstraint("status IN ('accepted', 'rejected')", name=op.f("ck_sync_event_status")),
        sa.CheckConstraint(
            "type IN ('module_progress', 'test_attempt', 'rollcall_status', 'survey_answer')",
            name=op.f("ck_sync_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["relayed_by"],
            ["app_user.id"],
            name=op.f("fk_sync_event_relayed_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_sync_event_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("client_event_id", name=op.f("pk_sync_event")),
    )
    op.create_index(
        "ix_sync_event_user_id_received_at", "sync_event", ["user_id", "received_at"], unique=False
    )
    op.create_table(
        "knowledge_pack_lesson",
        sa.Column("pack_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("lesson_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lesson.id"], name=op.f("fk_knowledge_pack_lesson_lesson_id_lesson")
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["knowledge_pack.id"],
            name=op.f("fk_knowledge_pack_lesson_pack_id_knowledge_pack"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pack_id", "lesson_id", name=op.f("pk_knowledge_pack_lesson")),
    )
    op.create_table(
        "knowledge_pack_media",
        sa.Column("pack_id", sa.UUID(), nullable=False),
        sa.Column("media_asset_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_asset.id"],
            name=op.f("fk_knowledge_pack_media_media_asset_id_media_asset"),
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["knowledge_pack.id"],
            name=op.f("fk_knowledge_pack_media_pack_id_knowledge_pack"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pack_id", "media_asset_id", name=op.f("pk_knowledge_pack_media")),
    )
    op.create_table(
        "lesson_assignment",
        sa.Column("slot_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lesson.id"], name=op.f("fk_lesson_assignment_lesson_id_lesson")
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["schedule_slot.id"],
            name=op.f("fk_lesson_assignment_slot_id_schedule_slot"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("slot_id", "date", name=op.f("pk_lesson_assignment")),
    )
    op.create_table(
        "module",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("part", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("duration_min", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("part IN ('shelter', 'main')", name=op.f("ck_module_part")),
        sa.CheckConstraint("duration_min BETWEEN 1 AND 10", name=op.f("ck_module_duration_range")),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lesson.id"],
            name=op.f("fk_module_lesson_id_lesson"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module")),
        sa.UniqueConstraint("lesson_id", "part", "position", name="uq_module_lesson_part_position"),
    )
    op.create_table(
        "rollcall_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("alert_event_id", sa.UUID(), nullable=True),
        sa.Column("opened_by", sa.UUID(), nullable=True),
        sa.Column("is_drill", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("opened_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["alert_event_id"],
            ["alert_event.id"],
            name=op.f("fk_rollcall_session_alert_event_id_alert_event"),
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_rollcall_session_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by"],
            ["app_user.id"],
            name=op.f("fk_rollcall_session_opened_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rollcall_session")),
    )
    op.create_index(
        "uq_rollcall_session_class_id_open",
        "rollcall_session",
        ["class_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "schedule_override",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("slot_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("starts_at", sa.Time(), nullable=True),
        sa.Column("ends_at", sa.Time(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('cancel', 'replace', 'extra')", name=op.f("ck_schedule_override_kind")
        ),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name=op.f("ck_schedule_override_time_order"),
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_schedule_override_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["schedule_slot.id"],
            name=op.f("fk_schedule_override_slot_id_schedule_slot"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subject.id"], name=op.f("fk_schedule_override_subject_id_subject")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_override")),
    )
    op.create_table(
        "test",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("window_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("window_hours", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "window_enabled = false OR window_hours IS NOT NULL", name=op.f("ck_test_window_hours")
        ),
        sa.CheckConstraint(
            "window_hours IN (24, 48, 72)", name=op.f("ck_test_window_hours_values")
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lesson.id"], name=op.f("fk_test_lesson_id_lesson"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test")),
    )
    op.create_table(
        "attempt",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_event_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("test_id", sa.UUID(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("completed_at_client", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("credit_status", sa.Text(), nullable=False),
        sa.Column("is_suspicious", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "credit_status IN ('credited', 'not_credited_late', 'not_credited_repeat')",
            name=op.f("ck_attempt_credit_status"),
        ),
        sa.ForeignKeyConstraint(
            ["client_event_id"],
            ["sync_event.client_event_id"],
            name=op.f("fk_attempt_client_event_id_sync_event"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["app_user.id"],
            name=op.f("fk_attempt_student_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["test_id"], ["test.id"], name=op.f("fk_attempt_test_id_test")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attempt")),
        sa.UniqueConstraint("client_event_id", name=op.f("uq_attempt_client_event_id")),
    )
    op.create_index(
        "uq_attempt_student_id_test_id_credited",
        "attempt",
        ["student_id", "test_id"],
        unique=True,
        postgresql_where=sa.text("credit_status = 'credited'"),
    )
    op.create_table(
        "card",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("media_asset_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('text', 'image', 'video')", name=op.f("ck_card_kind")),
        sa.ForeignKeyConstraint(
            ["media_asset_id"], ["media_asset.id"], name=op.f("fk_card_media_asset_id_media_asset")
        ),
        sa.ForeignKeyConstraint(
            ["module_id"], ["module.id"], name=op.f("fk_card_module_id_module"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card")),
        sa.UniqueConstraint("module_id", "position", name="uq_card_module_position"),
    )
    op.create_table(
        "module_progress",
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("module_id", sa.UUID(), nullable=False),
        sa.Column("progress_pct", sa.SmallInteger(), nullable=False),
        sa.Column("completed_at_client", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_event_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "progress_pct BETWEEN 0 AND 100", name=op.f("ck_module_progress_progress_range")
        ),
        sa.ForeignKeyConstraint(
            ["last_event_id"],
            ["sync_event.client_event_id"],
            name=op.f("fk_module_progress_last_event_id_sync_event"),
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["module.id"],
            name=op.f("fk_module_progress_module_id_module"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["app_user.id"],
            name=op.f("fk_module_progress_student_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("student_id", "module_id", name=op.f("pk_module_progress")),
    )
    op.create_table(
        "question",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("test_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answer_key", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("points", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('single', 'multiple')", name=op.f("ck_question_kind")),
        sa.ForeignKeyConstraint(
            ["test_id"], ["test.id"], name=op.f("fk_question_test_id_test"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question")),
        sa.UniqueConstraint("test_id", "position", name="uq_question_test_position"),
    )
    op.create_table(
        "rollcall_status",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("received_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_event_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "status IN ('safe', 'in_shelter')", name=op.f("ck_rollcall_status_status")
        ),
        sa.ForeignKeyConstraint(
            ["last_event_id"],
            ["sync_event.client_event_id"],
            name=op.f("fk_rollcall_status_last_event_id_sync_event"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["rollcall_session.id"],
            name=op.f("fk_rollcall_status_session_id_rollcall_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["app_user.id"],
            name=op.f("fk_rollcall_status_student_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", "student_id", name=op.f("pk_rollcall_status")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("rollcall_status")
    op.drop_table("question")
    op.drop_table("module_progress")
    op.drop_table("card")
    op.drop_index(
        "uq_attempt_student_id_test_id_credited",
        table_name="attempt",
        postgresql_where=sa.text("credit_status = 'credited'"),
    )
    op.drop_table("attempt")
    op.drop_table("test")
    op.drop_table("schedule_override")
    op.drop_index(
        "uq_rollcall_session_class_id_open",
        table_name="rollcall_session",
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.drop_table("rollcall_session")
    op.drop_table("module")
    op.drop_table("lesson_assignment")
    op.drop_table("knowledge_pack_media")
    op.drop_table("knowledge_pack_lesson")
    op.drop_index("ix_sync_event_user_id_received_at", table_name="sync_event")
    op.drop_table("sync_event")
    op.drop_index("ix_schedule_slot_class_id_weekday", table_name="schedule_slot")
    op.drop_table("schedule_slot")
    op.drop_table("push_subscription")
    op.drop_index("ix_parent_child_child_id", table_name="parent_child")
    op.drop_table("parent_child")
    op.drop_table("media_asset")
    op.drop_table("lesson")
    op.drop_table("knowledge_pack")
    op.drop_index("ix_class_membership_user_id", table_name="class_membership")
    op.drop_table("class_membership")
    op.drop_index("ix_alert_event_school_id_started_at", table_name="alert_event")
    op.drop_index(
        "ix_alert_event_active",
        table_name="alert_event",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_table("alert_event")
    op.drop_table("subject")
    op.drop_table("school_class")
    op.drop_table("app_user")
    op.drop_index("ix_school_region_code", table_name="school")
    op.drop_table("school")
    op.execute("DROP EXTENSION IF EXISTS citext")
