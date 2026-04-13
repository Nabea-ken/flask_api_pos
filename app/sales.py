from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload

from app import db
from app.models import Payment, Product, Sale

sales_bp = Blueprint("sales", __name__)


def _payment_to_dict(p: Payment):
    return {
        "id": p.id,
        "sale_id": p.sale_id,
        "trans_code": p.trans_code,
        "trans_amount": str(p.trans_amount),
        "phone_paid": p.phone_paid,
        "created_at": p.created_at.isoformat(),
    }


def _sale_to_dict(sale: Sale):
    payment = sale.payments[0] if sale.payments else None
    return {
        "id": sale.id,
        "product_id": sale.product_id,
        "created_at": sale.created_at.isoformat(),
        "payment": _payment_to_dict(payment) if payment else None,
    }


@sales_bp.route("/sales", methods=["GET", "POST"])
@jwt_required()
def sales():
    user_id = int(get_jwt_identity())

    if request.method == "GET":
        q = (
            Sale.query.options(joinedload(Sale.product), joinedload(Sale.payments))
            .join(Product)
            .filter(Product.user_id == user_id)
            .order_by(Sale.id)
        )
        rows = q.all()
        return jsonify([_sale_to_dict(s) for s in rows])

    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    trans_code = (data.get("trans_code") or "").strip()
    raw_amount = data.get("trans_amount")
    phone_paid = (data.get("phone_paid") or "").strip()

    if product_id is None:
        return jsonify({"error": "product_id is required"}), 400
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({"error": "product_id must be an integer"}), 400

    if not trans_code:
        return jsonify({"error": "trans_code is required"}), 400
    if raw_amount is None:
        return jsonify({"error": "trans_amount is required"}), 400
    if not phone_paid:
        return jsonify({"error": "phone_paid is required"}), 400

    try:
        trans_amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "trans_amount must be a number"}), 400

    product = Product.query.filter_by(id=product_id, user_id=user_id).first()
    if not product:
        return jsonify({"error": "product not found"}), 404

    sale = Sale(product_id=product.id)
    db.session.add(sale)
    db.session.flush()

    payment = Payment(
        sale_id=sale.id,
        trans_code=trans_code,
        trans_amount=trans_amount,
        phone_paid=phone_paid,
    )
    db.session.add(payment)
    db.session.commit()

    sale = (
        Sale.query.options(joinedload(Sale.payments))
        .filter_by(id=sale.id)
        .first()
    )
    return jsonify(_sale_to_dict(sale)), 201
