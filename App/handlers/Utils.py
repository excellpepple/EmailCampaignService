import base64
import datetime
import hashlib
import hmac
import json
import logging
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import jinja2
from bs4 import BeautifulSoup

from handlers.Schemas import Campaign, Contact

SECRET = os.environ.get("SECRET").encode()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_template( template_name: str ) -> jinja2.Template:
    """Load a Jinja2 template from the templates directory."""
    loader = jinja2.FileSystemLoader("templates")
    env = jinja2.Environment(loader=loader)
    return env.get_template(template_name)


def sign_token( payload: dict ) -> str:
    data = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        ).encode()

    signature = hmac.new(
        SECRET,
        data,
        hashlib.sha256,
        ).digest()

    return (
            base64.urlsafe_b64encode(data).decode()
            + "."
            + base64.urlsafe_b64encode(signature).decode()
    )


def verify_token( token: str ) -> dict | None:
    try:
        data_b64, signature_b64 = token.split(".", 1)

        data = base64.urlsafe_b64decode(data_b64)
        signature = base64.urlsafe_b64decode(signature_b64)

        expected = hmac.new(
            SECRET,
            data,
            hashlib.sha256,
            ).digest()

        if not hmac.compare_digest(signature, expected):
            return None

        result = json.loads(data)
        expires_at = datetime.datetime.fromisoformat(result["expires_at"])
        if datetime.datetime.now(datetime.UTC) > expires_at:
            return None
        return result

    except (ValueError, json.JSONDecodeError):
        return None


def format_message( message: str, data: dict ):
    environment = jinja2.Environment()
    template = environment.from_string(message)
    return template.render(**data)


def send_email( contact: Contact, campaign: Campaign, ses, data: dict ):
    sender = os.environ["EMAIL_SENDER"]
    recipient = str(contact.email)

    # Render the HTML with the contact's information
    message = format_message(campaign.body, data={ "name": contact.name, **data })

    # Convert HTML to plain text
    message_txt = BeautifulSoup(message, "html.parser").get_text(separator="\n", strip=True)

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
