"""SQLAlchemy-backed persistent run store for the workflow layer."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Float, ForeignKey, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    """Declarative base for AeroSynthX persistence models."""


class RunRow(Base):
    """One row per :class:`RunResult` persisted to disk."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    intent_text: Mapped[str] = mapped_column(String)
    intent_json: Mapped[str | None] = mapped_column(String, nullable=True)
    flow_state_json: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    case_dir: Mapped[str | None] = mapped_column(String, nullable=True)
    manifest_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at_iso: Mapped[str] = mapped_column(String)
    completed_at_iso: Mapped[str | None] = mapped_column(String, nullable=True)

    stages: Mapped[list[StageRow]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StageRow.ordinal",
    )
    xfoil_result: Mapped[XfoilResultRow | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class StageRow(Base):
    """One row per executed pipeline stage."""

    __tablename__ = "run_stages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    ordinal: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    duration_ms: Mapped[int] = mapped_column()
    output_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    run: Mapped[RunRow] = relationship(back_populates="stages")


class XfoilResultRow(Base):
    """One row per successful XFOIL analysis."""

    __tablename__ = "xfoil_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, unique=True)
    alpha_deg: Mapped[float] = mapped_column(Float)
    cl: Mapped[float] = mapped_column(Float)
    cd: Mapped[float] = mapped_column(Float)
    cm: Mapped[float] = mapped_column(Float)

    run: Mapped[RunRow] = relationship(back_populates="xfoil_result")


def _engine_for(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


def init_db(path: Path) -> None:
    """Create the database file and tables if they do not yet exist."""
    engine = _engine_for(path)
    Base.metadata.create_all(engine)
    engine.dispose()


@contextmanager
def open_session(path: Path) -> Iterator[Session]:
    """Yield a session bound to the SQLite file at ``path``.

    The schema is created on first use. The session is committed on
    normal exit and rolled back on exception.
    """
    engine = _engine_for(path)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()
