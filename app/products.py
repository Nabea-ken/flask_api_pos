from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models import Product

products_bp = Blueprint("products", __name__)


def _product_to_dict(p: Product):
    return {
        "id": p.id,
        "user_id": p.user_id,
        "name": p.name,
        "amount": str(p.amount),
        "created_at": p.created_at.isoformat(),
    }


@products_bp.route("/products", methods=["GET", "POST"])
@jwt_required()
def products():
    user_id = int(get_jwt_identity())

    if request.method == "GET":
        rows = Product.query.filter_by(user_id=user_id).order_by(Product.id).all()
        return jsonify([_product_to_dict(p) for p in rows])

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    raw_amount = data.get("amount")

    if not name:
        return jsonify({"error": "name is required"}), 400
    if raw_amount is None:
        return jsonify({"error": "amount is required"}), 400
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "amount must be a number"}), 400

    product = Product(user_id=user_id, name=name, amount=amount)
    db.session.add(product)
    db.session.commit()
    return jsonify(_product_to_dict(product)), 201
