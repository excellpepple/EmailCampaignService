import os
import json
from supabase import Client, create_client
import boto3
from pydantic import BaseModel, ValidationError
from .Exceptions import ContactListEmpty, TableValidationError, Error
from botocore.exceptions import ClientError

from .Schemas import Contact, Campaign
import logging
import jinja2
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def format_message(message:str, contact: Contact):
    envionment = jinja2.Environment()
    template = envionment.from_string(message)
    return template.render(name=contact.name)

def send_email(contact: Contact, campaign: Campaign, ses):
    sender = os.environ["EMAIL_SENDER"]
    recipient = str(contact.email)

    # Render the HTML with the contact's information
    message = format_message(campaign.body, contact)

    # Convert HTML to plain text
    message_txt = BeautifulSoup(message,"html.parser").get_text(separator="\n", strip=True)

    # Build MIME email
    email = MIMEMultipart("alternative")

    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = campaign.title

    # email["List-Unsubscribe"] = (
    #     f"<https://iheartpizza.biz/unsubscribe?token={unsubscribe_token}>"
    # )
    # Plain-text version
    email.attach(
        MIMEText(
            message_txt,
            "plain",
            "utf-8"
        )
    )

    # HTML version
    email.attach(
        MIMEText(
            message,
            "html",
            "utf-8"
        )
    )

    response = ses.send_raw_email(
        Source=sender,
        Destinations=[recipient],
        RawMessage={
            "Data": email.as_bytes()
        }
    )

    logger.info(
        "Email sent to %s, SES message: %s",
        recipient,
        response["MessageId"]
    )

    return response["MessageId"]

def handler(event, context):
    failures = []
    ses = boto3.client("ses")
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


