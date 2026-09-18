import os
import json
import datetime
from email.mime import message
from uuid import UUID, uuid4

import boto3
import supabase

from Schemas import Contact, DeletionRequest, DeletionResponse, UnsubscribeRequest, UnsubscribeResponse
import logging
import jinja2
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from supabase import Client, create_client
from Utils import load_template, send_email, verify_token, sign_token
from handlers.Schemas import Campaign
from settings import TEMPLATE_DATA

logger = logging.getLogger()
logger.setLevel(logging.INFO)

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY"),
    )
ses = boto3.client("ses", region_name="us-east-2")


def contact_subscribe( event, context ):
    """
    Subscribe a contact to the mailing list
    :method POST
    :route /contact/subscribe
    :body Contact
    :param event:
    :param context:
    :return:
    """
    try:
        body = json.loads(event["body"])
        contact = Contact.model_validate(body)
        contact.subscribed = True
        response = supabase.table("contact").upsert(contact.model_dump(mode="json"), on_conflict="email").execute()
        logger.info(f"Contact {contact.email} added to list\n Response: {response.data}")

        message_body = load_template("SubscriptionEmail.html")
        confirmation_message = Campaign(
            id=str(uuid4()), title=TEMPLATE_DATA["subscribed"]["title"], body=message_body.render(), tags=[],
            )
        send_email(contact, confirmation_message, ses)

    except Exception as e:
        logger.error(f"Something went wrong\n {e}")
        return {
            "statusCode": 500,
            "body":       json.dumps({ "message": "Something went wrong" })
            }

    return {
        "statusCode": 200,
        "body":       json.dumps({ "message": "Contacts Added to contact list" })
        }


def contact_unsubscribe( event, context ):
    """
    Unsubscribe a contact from the mailing list\n
    method POST\n
    route /contact/unsubscribe \n
    body UnsubscribeRequest
    :param event:
    :param context:
    :return:
    """
    logger.info(event)
    try:
        body = json.loads(event["body"])
        request = UnsubscribeRequest.model_validate(body)
        response = supabase.table("contact").select("*").eq("email", request.email).execute()
        if len(response.data) == 0:
            logger.warning(f"Contact {request.email} not found")
            return {
                "statusCode": 404,
                "body":       json.dumps({ "message": "Contact not found" })
                }
        contact = Contact.model_validate(response.data[0])

        now = datetime.datetime.now(datetime.UTC)
        token = sign_token(
            {
                "contact_id": contact.id,
                "created_at": now.isoformat(),
                "expires_at": (now + datetime.timedelta(days=7)).isoformat()
                },
            )
        confirmation_url = f"{os.environ.get("CONTACT_API_URL", "")}/unsubscribe/confirm?token={token}"
        message_body = load_template("UnsubscriptionConfirmation.html")
        confirmation_message = Campaign(
            id=str(uuid4()), title=TEMPLATE_DATA["unsubscribed"]["title"],
            body=message_body.render(), tags=[],
            )
        send_email(contact, confirmation_message, ses, { "url": confirmation_url })
    except Exception as e:
        logger.error(f"Something went wrong\n {e}")
        return {
            "statusCode": 500,
            "body":       json.dumps({ "message": "Something went wrong" })
            }

    return {
        "statusCode": 200,
        "body":       json.dumps(
            {
                "message": "Contacts Removed from contact list"
                },
            )
        }


def contact_unsubscribe_completed( event, context ):
    logger.info(event)
    try:
        body = json.loads(event["queryStringParameters"])
        request = UnsubscribeResponse.model_validate(body)
        contact_payload = verify_token(request.token)
        contact_id = contact_payload.get("contact_id", None) if contact_payload else None
        if contact_id is None:
            logger.warning(f"Invalid token")
            return {
                "statusCode": 400,
                "body": json.dumps({ "message": "Invalid token" })
                }

        response = supabase.table("contact").select("*").eq("id", contact_id).execute()
        if len(response.data) == 0:
            logger.warning(f"Contact not found")
            return {
                "statusCode": 404,
                "body": json.dumps({ "message": "Contact not found" })
                }
        contact = Contact.model_validate(response.data[0])
        contact.subscribed = False
        supabase.table("contact").upsert(contact.model_dump(mode="json"), on_conflict="email").execute()
        message_body = load_template("UnsubscribeCompleted.html")
        deletion_message = Campaign(
            id=str(uuid4()), title=TEMPLATE_DATA["unsubscribed_completed"]["title"],
            body=message_body.render(), tags=[],
            )
        send_email(contact, deletion_message, ses)

    except Exception as e:
        logger.error(f"Something went wrong\n {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({ "message": "Something went wrong" })
            }

    return {
        "statusCode": 200,
        "body":       json.dumps(
            {
                "message": "Contacts Removed from contact list"
                },
            )
        }


def contact_delete( event, context ):
    logger.info(event)
    try:
        body = json.loads(event["body"])
        request = DeletionRequest.model_validate(body)
        response = supabase.table("contact").select("*").eq("email", request.email).execute()
        if len(response.data) == 0:
            logger.warning(f"Contact {request.email} not found")
            return {
                "statusCode": 404,
                "body": json.dumps({ "message": "Contact not found" })
                }
        contact = Contact.model_validate(response.data[0])

        now = datetime.datetime.now(datetime.UTC)
        token = sign_token(
            {
                "contact_id": contact.id,
                "delegated":  request.delegated,
                "created_at": now.isoformat(),
                "expires_at": (now + datetime.timedelta(days=7)).isoformat()
                },
            )
        confirmation_url = f"{os.environ.get("CONTACT_API_URL", "")}/delete/confirm?token={token}"
        message_body = load_template("DeletionConfirmation.html")
        confirmation_message = Campaign(
            id=str(uuid4()), title=TEMPLATE_DATA["deletion_requested"]["title"],
            body=message_body.render(), tags=[],
            )
        send_email(contact, confirmation_message, ses, { "url": confirmation_url })
        if request.delegated:
            contact.shouldDelete = True
            supabase.table("contact").upsert(contact.model_dump(mode="json"), on_conflict="email").execute()
        else:
            supabase.table("contact").delete().eq("email", request.email).execute()
    except Exception as e:
        logger.error(f"Something went wrong\n {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({ "message": "Something went wrong" })
            }


    return {
        "statusCode": 200,
        "body":       json.dumps(
            {
                "message": "Contacts Removed from contact list"
                },
            )
        }


def contact_delete_confirmed( event, context ):
    logger.info(event)
    try:
        body = json.loads(event["queryStringParameters"])
        request = DeletionResponse.model_validate(body)
        contact_payload = verify_token(request.token)
        contact_id = contact_payload.get("contact_id", None) if contact_payload else None
        if contact_id is None:
            logger.warning(f"Invalid token")
            return {
                "statusCode": 400,
                "body": json.dumps({ "message": "Invalid token" })
                }

        response = supabase.table("contact").select("*").eq("id", contact_id).execute()
        if len(response.data) == 0:
            logger.warning(f"Contact not found")
            return {
                "statusCode": 404,
                "body": json.dumps({ "message": "Contact not found" })
            }
        contact = Contact.model_validate(response.data[0])
        temp = contact.model_copy()
        delegated = contact_payload.get("delegated", None) if contact_payload else False
        if delegated:
            contact.shouldDelete = True
            supabase.table("contact").upsert(contact.model_dump(mode="json"), on_conflict="email").execute()
        else:
            supabase.table("contact").delete().eq("email", contact.email).execute()
        message_body = load_template("DeletionCompleted.html")
        confirmation_message = Campaign(
            id=str(uuid4()), title=TEMPLATE_DATA["deletion"]["title"],
            body=message_body.render(), tags=[],
            )
        temp.shouldDelete = False
        temp.subscribed = True
        send_email(temp, confirmation_message, ses)


    except Exception as e:
        logger.error(f"Something went wrong\n {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({ "message": "Something went wrong" })
            }


    return {
        "statusCode": 200,
        "body":       json.dumps(
            {
                "message": "Contacts Removed from contact list"
                },
            )
        }
