from pathlib import Path

import pytest

from app import create_app
from database import db
from models import Sign


@pytest.fixture
def app(tmp_path: Path):
    db_path = tmp_path / "test_signage.db"
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add_all(
            [
                Sign(category="Mesh Short", name="Events.SC", total_quantity=10, description="Test item"),
                Sign(category="Equipment", name="Marquee 3x3", total_quantity=2, description="Test item"),
                Sign(category="Vinyl & Corflutes", name="Corflute", total_quantity=13, description="Test item"),
            ]
        )
        db.session.commit()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
