"""
LF1 - Visitor Identification Handler
SmartDoor Authentication System

Triggered by the Kinesis Data Stream that Rekognition Video writes its
face-search results to. Decides the workflow for each detected face:

  - Unknown face            -> store a snapshot reference + notify the owner
                               via SNS with a registration link
  - Known but unregistered  -> reply with a registration link
  - Registered visitor      -> invoke the OTP generator (LF2)

All account-specific values are read from environment variables, so no
secrets or hard-coded ARNs live in the source.
"""

import os
import json
import base64
import datetime

import boto3

# -- Configuration (set as Lambda environment variables) ---------------------
VISITORS_TABLE = os.environ.get("VISITORS_TABLE", "visitors")
SEND_OTP_LAMBDA = os.environ.get("SEND_OTP_LAMBDA", "smartdoor-send-otp")
BUCKET = os.environ["BUCKET"]                       # e.g. my-smartdoor-bucket
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]         # arn:aws:sns:<region>:<acct>:<topic>
WEBSITE_BASE = os.environ.get(                      # S3 static-site base URL
    "WEBSITE_BASE",
    f"http://{BUCKET}.s3-website-us-east-1.amazonaws.com",
)

# -- AWS clients -------------------------------------------------------------
dynamo = boto3.resource("dynamodb")
visitors_table = dynamo.Table(VISITORS_TABLE)
lambda_client = boto3.client("lambda")
sns = boto3.client("sns")


def _parse_record(event):
    """Decode a Kinesis record (base64 JSON) or accept a console test dict."""
    record = event["Records"][0]["kinesis"]["data"]
    if isinstance(record, dict):
        return record
    decoded = base64.b64decode(record).decode("utf-8")
    return json.loads(decoded)


def lambda_handler(event, context):
    print("EVENT RECEIVED:", json.dumps(event)[:1000])

    try:
        data = _parse_record(event)
    except Exception as e:
        print("Error decoding record:", str(e))
        return {"statusCode": 400, "body": f"Invalid Kinesis record: {e}"}

    face_response = data.get("FaceSearchResponse", [])
    matched = face_response[0].get("MatchedFaces", []) if face_response else []

    # -- Unknown visitor -----------------------------------------------------
    if not matched:
        fragment = (
            data.get("InputInformation", {})
            .get("KinesisVideo", {})
            .get("FragmentNumber", "unknown")
        )
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        s3_key = f"unknown_visitors/{timestamp}_{fragment}.jpg"
        image_url = f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
        face_id = f"unknown-{timestamp}-{fragment}"
        registration_link = (
            f"{WEBSITE_BASE}/visitor_registration.html"
            f"?faceId={face_id}&fileName={s3_key}"
        )

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="SmartDoor: New Visitor Detected",
            Message=(
                "Unknown visitor detected at your door.\n\n"
                f"Visitor snapshot: {image_url}\n"
                f"Register visitor here: {registration_link}"
            ),
        )
        print(f"Unknown visitor {face_id}: registration link sent via SNS.")
        return {"statusCode": 200, "body": "Unknown visitor notification sent"}

    # -- Known face ----------------------------------------------------------
    face_id = matched[0]["Face"]["FaceId"]
    visitor = visitors_table.get_item(Key={"faceId": face_id}).get("Item")

    if not visitor:
        registration_link = f"{WEBSITE_BASE}/visitor_registration.html?faceId={face_id}"
        print(f"Face {face_id} recognised but not registered: {registration_link}")
        return {"statusCode": 200, "body": "Visitor not registered"}

    # -- Registered visitor: trigger OTP (LF2) -------------------------------
    lambda_client.invoke(
        FunctionName=SEND_OTP_LAMBDA,
        InvocationType="Event",
        Payload=json.dumps({"faceId": face_id}),
    )
    otp_page = f"{WEBSITE_BASE}/otp_validation.html?faceId={face_id}"
    print(f"Registered visitor {face_id}: OTP triggered.")
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "OTP triggered", "otp_page": otp_page}),
    }
