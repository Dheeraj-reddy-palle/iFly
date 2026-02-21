from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Index
from sqlalchemy.sql import func
from app.database import Base

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(50), unique=True, nullable=False)
    trained_at = Column(DateTime, nullable=False)
    train_r2 = Column(Float, nullable=True)
    test_r2 = Column(Float, nullable=True)
    test_mae = Column(Float, nullable=True)
    test_rmse = Column(Float, nullable=True)
    deployed = Column(Boolean, default=False, nullable=False)
    file_path = Column(Text, nullable=False)
    is_candidate = Column(Boolean, default=False, nullable=False)
    compared_against_version = Column(String(50), nullable=True)
    compared_on_timestamp = Column(DateTime, nullable=True)
    __table_args__ = (
        Index(
            'one_deployed_model',
            'deployed',
            unique=True,
            postgresql_where=(deployed == True)
        ),
    )
