from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'roadguard.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Defect(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    defect_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)
    urgency_level: Mapped[str] = mapped_column(String(10), nullable=False)
    surface_area_sqm: Mapped[float] = mapped_column(Float, nullable=False)
    patch_depth_m: Mapped[float] = mapped_column(Float, nullable=False)
    asphalt_volume_m3: Mapped[float] = mapped_column(Float, nullable=False)
    asphalt_weight_tonnes: Mapped[float] = mapped_column(Float, nullable=False)
    bags_25kg: Mapped[int] = mapped_column(Integer, nullable=False)
    tack_coat_liters: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    telemetry_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("defects")}
        if "estimated_cost_inr" not in columns:
            connection.execute(
                text("ALTER TABLE defects ADD COLUMN estimated_cost_inr FLOAT")
            )
            connection.execute(
                text(
                    "UPDATE defects SET estimated_cost_inr = estimated_cost_usd * 83.0 "
                    "WHERE estimated_cost_inr IS NULL"
                )
            )