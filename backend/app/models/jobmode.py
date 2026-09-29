import enum


class JobMode(str, enum.Enum):
    BULLET = "bullet"
    TABLE = "table"
    CONCEPT = "concept"
