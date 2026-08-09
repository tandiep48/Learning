"""
entity/translation/entity.py
-----------------------------
SQLAlchemy ORM model for the `translation` table — per-line CN/VN/EN
translations keyed by a translation_id like "H1_2_3".
"""

from sqlalchemy import Column, String, Text
from entity.database import Base


class Translation(Base):
    __tablename__ = "translation"

    translation_id = Column(String, primary_key=True)
    cn = Column(Text, nullable=True)
    vn = Column(Text, nullable=True)
    en = Column(Text, nullable=True)
