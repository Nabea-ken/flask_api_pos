"""M-Pesa STK integration endpoints."""

import base64
import math
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from requests.auth import HTTPBasicAuth

mpesa_bp = Blueprint("mpesa", __name__)


def _get_mpesa_config():
    config = {
        "consumer_key": os.environ.get("MPESA_CONSUMER_KEY"),
        "consumer_secret": os.environ.get("MPESA_CONSUMER_SECRET"),
        "short_code": os.environ.get("MPESA_SHORTCODE"),
        "pass_key": os.environ.get("MPESA_PASS_KEY"),
        "callback_url": os.environ.get("MPESA_CALLBACK_URL"),
        "access_token_url": os.environ.get(
            "MPESA_ACCESS_TOKEN_URL",
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
        ),
        "stk_push_url": os.environ.get(
            "MPESA_STK_PUSH_URL",
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        ),
        "stk_query_url": os.environ.get(
            "MPESA_STK_QUERY_URL",
            "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query",
        ),
    }
    required = (
        "consumer_key",
        "consumer_secret",
        "short_code",
        "pass_key",
    )
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError(
            "Missing M-Pesa configuration: "
            + ", ".join(f"MPESA_{m.upper()}" for m in missing)
        )
    return config


def _timestamp_now():
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _generate_password(short_code, pass_key, timestamp):
    password_string = f"{short_code}{pass_key}{timestamp}"
    return base64.b64encode(password_string.encode("utf-8")).decode("utf-8")


def _get_access_token(config):
    response = requests.get(
        config["access_token_url"],
        auth=HTTPBasicAuth(config["consumer_key"], config["consumer_secret"]),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise ValueError("M-Pesa token response did not include access_token")
    return token


def _normalize_phone(phone_number):
    return str(phone_number).strip().replace("+", "")


@mpesa_bp.route("/mpesa/stk-push", methods=["POST"])
@jwt_required()
def stk_push():
    data = request.get_json(silent=True) or {}
    phone_number = data.get("phone_number")
    amount = data.get("amount")
    account_reference = (data.get("account_reference") or "flask-api-pos").strip()
    transaction_desc = (data.get("transaction_desc") or "Payment").strip()

    if not phone_number:
        return jsonify({"error": "phone_number is required"}), 400
    if amount is None:
        return jsonify({"error": "amount is required"}), 400

    try:
        amount_value = math.ceil(Decimal(str(amount)))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "amount must be numeric"}), 400
    if amount_value <= 0:
        return jsonify({"error": "amount must be greater than zero"}), 400

    try:
        config = _get_mpesa_config()
        callback_url = config.get("callback_url")
        if not callback_url:
            raise ValueError("Missing MPESA_CALLBACK_URL")

        timestamp = _timestamp_now()
        password = _generate_password(config["short_code"], config["pass_key"], timestamp)
        token = _get_access_token(config)

        payload = {
            "BusinessShortCode": config["short_code"],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount_value),
            "PartyA": _normalize_phone(phone_number),
            "PartyB": config["short_code"],
            "PhoneNumber": _normalize_phone(phone_number),
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        response = requests.post(
            config["stk_push_url"],
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except requests.RequestException as e:
        return jsonify({"error": "M-Pesa request failed", "details": str(e)}), 502

    return jsonify(response.json()), 200


@mpesa_bp.route("/mpesa/stk-query", methods=["POST"])
@jwt_required()
def stk_query():
    data = request.get_json(silent=True) or {}
    checkout_request_id = (data.get("checkout_request_id") or "").strip()

    if not checkout_request_id:
        return jsonify({"error": "checkout_request_id is required"}), 400

    try:
        config = _get_mpesa_config()
        timestamp = _timestamp_now()
        password = _generate_password(config["short_code"], config["pass_key"], timestamp)
        token = _get_access_token(config)

        payload = {
            "BusinessShortCode": config["short_code"],
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        response = requests.post(
            config["stk_query_url"],
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except requests.RequestException as e:
        return jsonify({"error": "M-Pesa request failed", "details": str(e)}), 502

    return jsonify(response.json()), 200


@mpesa_bp.route("/mpesa/stk-callback", methods=["POST"])
def stk_callback():
    """Public callback endpoint that Safaricom posts to after STK flow."""
    callback_data = request.get_json(silent=True) or {}
    # In production, persist callback_data and verify expected fields/signature rules.
    return jsonify({"ok": True, "received": callback_data}), 200