"""SQLAlchemy ORM models mirroring the legacy SQLite schema."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


class RunModel(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class TraceNodeModel(Base):
    __tablename__ = "trace_nodes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    span_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String, nullable=True)
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class SpanEventModel(Base):
    __tablename__ = "span_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
