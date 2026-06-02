"""
LF4 - OTP Validator
SmartDoor Authentication System

Backs the `POST /validate-otp` API Gateway endpoint that the OTP validation
web page calls. Checks the submitted passcode against the `passcodes` table,
verifies it has not expired, looks up the visitor, and returns the access
decision: granted / denied / expired.
"""

import os
import json
import time

import boto3

PASSCODES_TABLE = os.environ.get("PASSCODES_TABLE", "passcodes")
VISITORS_TABLE = os.environ.get("VISITORS_TABLE", "visitors")

dynamo = boto3.resource("dynamodb")
passcodes_table = dynamo.Table(PASSCODES_TABLE)
visitors_table = dynamo.Table(VISITORS_TABLE)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}


def _respond(status, payload):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(payload)}


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return _respond(200, {"message": "ok"})

    try:
        body = event.get("body")
        body = json.loads(body) if isinstance(body, str) else (body or {})
        passcode = body.get("passcode")
    except Exception:
        return _respond(400, {"error": "Invalid JSON input"})

    if not passcode:
        return _respond(400, {"error": "OTP missing"})

    try:
        record = passcodes_table.get_item(Key={"passcode": passcode}).get("Item")
    except Exception as e:
        return _respond(500, {"error": f"Error fetching OTP: {e}"})

    if not record:
        return _respond(200, {"access": "denied"})

    # Expiry check - the OTP record stores an `expires` epoch timestamp.
    expires = record.get("expires")
    if expires is not None and int(time.time()) > int(expires):
        return _respond(200, {"access": "expired"})

    face_id = record.get("faceId")
    if not face_id:
        return _respond(200, {"access": "denied"})

    visitor = visitors_table.get_item(Key={"faceId": face_id}).get("Item")
    visitor_name = visitor.get("name", "Guest") if visitor else "Guest"

    return _respond(200, {"access": "granted", "visitorName": visitor_name})
