import os

from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    BundlingOptions,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_lambda as lambda_,
    aws_lambda_event_sources as events,
)


from dotenv import load_dotenv
class AppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        load_dotenv()
        # Queues
        campaign_queue = sqs.Queue(
            self, "CampaignQueue",
            queue_name="CampaignQueue",
            visibility_timeout=Duration.seconds(300)
        )
        deadletter_email_queue = sqs.Queue(
            self, "DeadletterEmailQueue",
            queue_name="DeadletterEmailQueue",
            visibility_timeout=Duration.seconds(300),
        )
        email_queue = sqs.Queue(
            self, "EmailQueue",
            queue_name="EmailQueue",
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=deadletter_email_queue,
            ),
        )


        # Lambda
        email_handler = lambda_.Function(
            self, "EmailHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="EmailHandler.handler",
            code=lambda_.Code.from_asset(
                "handlers",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_14.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && "
                        "cp -r . /asset-output"
                    ],
                ),
            ),
            environment={
                "EMAIL_SENDER": os.environ.get("EMAIL_SENDER"),
            }
        )
        email_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendRawEmail"],
                resources=["*"]
            )
        )

        sqs_events_source_email = events.SqsEventSource(email_queue, batch_size=10, report_batch_item_failures=True)
        email_handler.add_event_source(sqs_events_source_email)

        campaign_handler = lambda_.Function(
            self, "CampaignHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="CampaignHandler.handler",
            code=lambda_.Code.from_asset(
                "handlers",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_14.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && "
                        "cp -r . /asset-output"
                    ],
                ),
            ),
            environment={
                "EMAIL_QUEUE_URL": email_queue.queue_url,
                "SUPABASE_URL": os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY": os.environ.get("SUPABASE_KEY"),
            },
            timeout=Duration.seconds(30),
        )
        sqs_event_source_campsign = events.SqsEventSource(campaign_queue)
        campaign_handler.add_event_source(sqs_event_source_campsign)

        campaign_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:sendmessage"],
                resources=["*"]
            )
        )


