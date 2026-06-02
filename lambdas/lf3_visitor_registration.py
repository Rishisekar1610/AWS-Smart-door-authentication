"""
LF3 - Visitor Registration Handler
SmartDoor Authentication System

Backs the `POST /visitor-information` API Gateway endpoint that the visitor
registration web page calls. Stores the visitor in the `visitors` table and
marks them authorized, so future detections go straight to the OTP flow.

NOTE: In the original project report, the appendix code labelled "Lambda
Function 3" was actually a duplicate of LF1 (the identification handler).
This file is the registration handler that the documented API contract and
the registration page (visitor_registration.html -> /visitor-information)
actually require.
"""

import os
import json
import datetime

import boto3

VISITORS_TABLE = os.environ.get("VISITORS_TABLE", "visitors")
dynamo = boto3.resource("dynamodb")
visitors_table = dynamo.Table(VISITORS_TABLE)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
}


def _respond(status, payload):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(payload)}


def lambda_handler(event, context):
    # CORS pre-flight
    if event.get("httpMethod") == "OPTIONS":
        return _respond(200, {"message": "ok"})

    try:
        body = event.get("body")
        body = json.loads(body) if isinstance(body, str) else (body or {})
    except Exception:
        return _respond(400, {"error": "Invalid JSON input"})

    face_id = body.get("faceId")
    name = body.get("name")
    email = body.get("email")
    file_name = body.get("fileName")  # optional S3 snapshot key

    if not face_id or not name or not email:
        return _respond(400, {"error": "faceId, name and email are required"})

    item = {
        "faceId": face_id,
        "name": name,
        "email": email,
        "authorized": True,
        "registeredAt": datetime.datetime.utcnow().isoformat(),
    }
    if file_name:
        item["photoKey"] = file_name

    visitors_table.put_item(Item=item)
    print(f"Registered visitor {name} ({face_id})")
    return _respond(200, {"message": "Visitor registered successfully", "faceId": face_id})
