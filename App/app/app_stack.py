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
    aws_certificatemanager as acm,
    aws_apigatewayv2 as apigateway,
    aws_apigatewayv2_integrations as HttpLambdaIntegration,
    )

from dotenv import load_dotenv

load_dotenv()


class AppStack(Stack):

    def __init__( self, scope: Construct, construct_id: str, **kwargs ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Queues
        campaign_queue = sqs.Queue(
            self, "CampaignQueue",
            queue_name="CampaignQueue",
            visibility_timeout=Duration.seconds(300),
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
                },
            )
        email_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendRawEmail"],
                resources=["*"],
                ),
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                },
            timeout=Duration.seconds(30),
            )
        sqs_event_source_campsign = events.SqsEventSource(campaign_queue)
        campaign_handler.add_event_source(sqs_event_source_campsign)

        campaign_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:sendmessage"],
                resources=["*"],
                ),
            )


class ContactAPIStack(Stack):

    def __init__( self, scope: Construct, construct_id: str, **kwargs ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        subscribe_handler = lambda_.Function(
            self, "SubscribeHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="ContactsHandler.contact_subscribe",
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                "CONTACT_API_URL": os.environ.get("CONTACT_API_URL"),
                },

            )

        unsubscribe_handler = lambda_.Function(
            self, "UnsubscribeHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="ContactsHandler.contact_unsubscribe",
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                "CONTACT_API_URL": os.environ.get("CONTACT_API_URL"),
                },

            )

        unsubscribe_completed_handler = lambda_.Function(
            self, "UnsubscribCompletedHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="ContactsHandler.contact_unsubscribe_completed",
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                "CONTACT_API_URL": os.environ.get("CONTACT_API_URL"),
                },
            )

        deletion_handler = lambda_.Function(
            self, "DeletionHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="ContactsHandler.contact_delete",
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                "CONTACT_API_URL": os.environ.get("CONTACT_API_URL"),
                },

            )
        deletion_completed_handler = lambda_.Function(
            self, "DeletionCompletedHandler",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="ContactsHandler.contact_delete_confirmed",
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
                "SUPABASE_URL":    os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY":    os.environ.get("SUPABASE_KEY"),
                "CONTACT_API_URL": os.environ.get("CONTACT_API_URL"),
                },

            )
        # Domain Certification and API Gateway
        domain_name = os.environ.get("DOMAIN_NAME")
        if domain_name is None:
            raise ValueError("DOMAIN_NAME environment variable is not set")

        cert = acm.Certificate(
            self, "ContactsApiCertificate",
            domain_name=domain_name,
            validation=acm.CertificateValidation.from_dns(),
            )

        dn = apigateway.DomainName(
            self, "DN",
            domain_name=domain_name,
            certificate=cert,
            )

        api = apigateway.HttpApi(
            self, "ContactsApi",
            default_domain_mapping=apigateway.DomainMappingOptions(domain_name=dn),
            default_throttle=apigateway.ThrottleSettings(burst_limit=100, rate_limit=50),
            )

        api.add_routes(
            path="/contact",
            methods=[apigateway.HttpMethod.POST, apigateway.HttpMethod.PUT],
            integration=HttpLambdaIntegration.HttpLambdaIntegration(
                "SubscribeIntegration",
                subscribe_handler,
                )
            )

        api.add_routes(
            path="/contact/unsubscribe",
            methods=[apigateway.HttpMethod.POST],
            integration=HttpLambdaIntegration.HttpLambdaIntegration(
                "UnsubscribeIntegration",
                unsubscribe_handler,
                )
            )

        api.add_routes(
            path="/contact/unsubscribe/confirm",
            methods=[apigateway.HttpMethod.POST],
            integration=HttpLambdaIntegration.HttpLambdaIntegration(
                "UnsubscribeCompletedIntegration",
                unsubscribe_completed_handler,
                )

            )

        api.add_routes(
            path="/contact/delete",
            methods=[apigateway.HttpMethod.POST],
            integration=HttpLambdaIntegration.HttpLambdaIntegration(
                "DeletionIntegration",
                deletion_handler,
                )
            )
        api.add_routes(
            path="/contact/delete/confirm",
            methods=[apigateway.HttpMethod.DELETE],
            integration=HttpLambdaIntegration.HttpLambdaIntegration(
                "DeletionCompletedIntegration",
                deletion_completed_handler,
                )
            )


