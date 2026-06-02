"""
LF2 - OTP Generator
SmartDoor Authentication System

Invoked asynchronously by LF1 with a payload {"faceId": "..."}.
Looks the visitor up, generates a short-lived one-time passcode, stores it in
the `passcodes` table with an expiry, and emails it to the owner/visitor
through SNS.
"""

import os
import time
import random

import boto3

VISITORS_TABLE = os.environ.get("VISITORS_TABLE", "visitors")
PASSCODES_TABLE = os.environ.get("PASSCODES_TABLE", "passcodes")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
OTP_TTL_SECONDS = int(os.environ.get("OTP_TTL_SECONDS", "300"))  # default 5 minutes

dynamo = boto3.resource("dynamodb")
visitors_table = dynamo.Table(VISITORS_TABLE)
passcodes_table = dynamo.Table(PASSCODES_TABLE)
sns = boto3.client("sns")


def lambda_handler(event, context):
    face_id = event["faceId"]
    print(f"Looking up visitor for FaceId: {face_id}")

    response = visitors_table.get_item(Key={"faceId": face_id})
    if "Item" not in response:
        print("Visitor not found in DynamoDB")
        return {"statusCode": 404, "body": "Visitor not found"}

    visitor = response["Item"]
    name = visitor.get("name", "Guest")
    email = visitor.get("email", "unknown@example.com")

    otp = f"{random.randint(1000, 9999)}"            # 4-digit OTP
    expires = int(time.time()) + OTP_TTL_SECONDS

    passcodes_table.put_item(
        Item={"passcode": otp, "faceId": face_id, "expires": expires}
    )
    print(f"OTP {otp} stored for FaceId {face_id} (expires {expires})")

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="Your Smart Door OTP",
        Message=(
            f"Hello {name},\n"
            f"Your OTP is: {otp}\n"
            f"Valid for {OTP_TTL_SECONDS // 60} minutes."
        ),
    )
    print(f"OTP sent to {email}")
    return {"statusCode": 200, "body": f"OTP sent to {email}"}
