import os
import json
import boto3

from Schemas import Contact, Campaign
import logging
import jinja2
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from handlers.Utils import send_email

logger = logging.getLogger()
logger.setLevel(logging.INFO)



def handler(event, context):
    failures = []
    ses = boto3.client("ses", region_name="us-east-2") #TODO: Make sure stack is running on us-east-2
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])

            contact = Contact.model_validate(body["contact"])
            campaign = Campaign.model_validate(body["message"])

            send_email(contact, campaign, ses)



        except Exception:
            logger.exception(
                "Failed to process %s",
                record["messageId"],
            )

            failures.append({
                "itemIdentifier": record["messageId"]
            })


    return {
        "batchItemFailures": failures
    }


