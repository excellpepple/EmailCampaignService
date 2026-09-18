
import os
import json
from supabase import Client, create_client
import boto3
from pydantic import BaseModel, ValidationError
from Exceptions import ContactListEmpty, TableValidationError, Error
from Schemas import Contact, Campaign
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_batch_with_retry(sqs, queue_url, entries, max_retries=5):
    """
    Send a batch of messages to SQS with retry logic.
    :param sqs:
    :param queue_url:
    :param entries:
    :param max_retries:
    :return: None
    """
    remaining = entries

    for attempt in range(max_retries):
        response = sqs.send_message_batch(
            QueueUrl=queue_url,
            Entries=remaining,
        )

        failed_ids = {
            failure["Id"]
            for failure in response.get("Failed", [])
        }

        if not failed_ids:
            return

        remaining = [
            entry
            for entry in remaining
            if entry["Id"] in failed_ids
        ]

        logger.warning(
            "Attempt %d failed for %d messages",
            attempt + 1,
            len(remaining),
            )

    raise RuntimeError(
        f"Failed to send {len(remaining)} SQS messages after "
        f"{max_retries} attempts"
    )


def create_campaign(campaign: Campaign):
    """
    Create a campaign and send it to all contacts in the database
    :param campaign:
    :return:
    """
    supabase: Client = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_KEY")
    )
    logger.info("Creating campaign %s", campaign.id)
    logger.info("DB Client created")
    sqs = boto3.client("sqs")
    email_queue_url = os.environ.get("EMAIL_QUEUE_URL")

    response = supabase.table("contact").select("*").execute()
    logger.info(response)
    if response.data is None:
        logger.error("Unable to retrieve a response from database")
        raise TableValidationError("Unable to retrieve a response from database")

    contact_list = response.data
    if not contact_list:
        logger.error("Unable to retrieve a response from database")
        raise ContactListEmpty("Failed to find contacts in database")

    batch = []
    for raw_contact in contact_list:
        contact = Contact.model_validate(raw_contact)
        if not contact.subscribed or contact.shouldDelete:
            continue #Skipping contact

        #filter out tags if campaign has a tag
        if campaign.tags:
            has_tags = False
            for tag in campaign.tags:
                if tag in contact.tags:
                    logger.info(f"Found tag {tag} in campaign {campaign.id} for {contact.email}")
                    has_tags = True
                    break
            if not has_tags:
                continue


        logger.info(f"Processing contact {contact.email}")
        batch.append({
            "Id": contact.id,
            "MessageBody": json.dumps({
                "contact": contact.model_dump(mode="json"),
                "message": campaign.model_dump(mode="json")
            })
        })

        if len(batch) == 10:
            logger.info("Bath ready for SES")
            response = sqs.send_message_batch(
                QueueUrl=email_queue_url,
                Entries=batch,
            )
            logger.info(f"Response: {response}")
            batch = []
    if batch:
        logger.info("Sending last batch for SES")
        response = sqs.send_message_batch(
            QueueUrl=email_queue_url,
            Entries=batch,
        )
        logger.info(f"Response: {response}")


def handler(event, context):
    """
    Lambda function to handle campaign creation
    :param event:
    :param context:
    :return:
    """
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            campaign = Campaign.model_validate(body)
        except (json.JSONDecodeError, ValidationError) as e:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Invalid Campaign",
                    "details": str(e)
                }),
            }

        try:
            create_campaign(campaign)


        except TableValidationError as e:
            logger.error(f"Failed to create a campaign for {campaign.id}, reason: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Failed to create campaign",
                })
            }
        except ContactListEmpty as e:
            logger.warning(f"Failed to create a campaign for {campaign.id} because contact list is empty error: {str(e)}")


        except Exception as e:
            logger.error(f"Something went wrong with creating a campaign for {campaign.id} error: {str(e)}")
            

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Campaign created successfully",
        })
    }

