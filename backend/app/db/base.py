from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Models live in `ai_platform.memory.models` (conversation storage) and,
    from Milestone 4 onward, `domains.finance.*` — this class is the one
    place both depend on.
    """
