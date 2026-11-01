from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from . import config

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {},
)


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
