"""Flask application factory for flask-api-pos."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()


def _load_env():
    """Load `.env` from project root (directory containing this package's parent)."""
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")


def create_app():
    _load_env()

    secret_key = os.environ.get("SECRET_KEY")
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    database_uri = os.environ.get("SQLALCHEMY_DATABASE_URI")

    missing = [
        name
        for name, val in (
            ("SECRET_KEY", secret_key),
            ("JWT_SECRET_KEY", jwt_secret),
            ("SQLALCHEMY_DATABASE_URI", database_uri),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and set them."
        )

    app = Flask(__name__)
    app.config["SECRET_KEY"] = secret_key
    app.config["JWT_SECRET_KEY"] = jwt_secret
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    jwt.init_app(app)

    from app import models  # noqa: F401
    from app.auth import auth_bp
    from app.products import products_bp
    from app.sales import sales_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(sales_bp)

    with app.app_context():
        db.create_all()

    return app
