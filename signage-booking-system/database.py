import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


db = SQLAlchemy()


def get_database_path() -> str:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, "signage.db")


def init_app(app) -> None:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{get_database_path()}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)


def ensure_schema_updates() -> None:
    inspector = db.inspect(db.engine)
    if not inspector.has_table("signs"):
        return

    sign_columns = {column["name"] for column in inspector.get_columns("signs")}
    if "category" not in sign_columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE signs ADD COLUMN category VARCHAR(120)"))
