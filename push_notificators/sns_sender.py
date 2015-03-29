try:
    import ujson as json
except ImportError:
    import json

import boto.sns
from repoze.lru import lru_cache


class SNSResponseError(Exception):
    """docstring for SNSResponseError"""
    def __init__(self, value):
        super(SNSResponseError, self).__init__()
        self.value = value


class SNSArn(object):
    """docstring for SNSArn"""
    def __init__(self, arn_string):
        super(SNSArn, self).__init__()
        arn_parts = arn_string.split(":")
        if len(arn_parts) != 6:
            raise ValueError("Wrong arn_string format")

        if arn_parts[0] != "arn":
            raise ValueError("%s isn't arn" % arn_string)

        if arn_parts[1] != "aws":
            raise ValueError("%s isn't aws arn" % arn_string)

        self.arn_string = arn_string
        self.service = arn_parts[2]
        self.region = arn_parts[3]
        self.namespace = arn_parts[4]
        app_url_parts = arn_parts[5].split("/")
        self.platform = app_url_parts[1]
        self.app_name = app_url_parts[2]


class SNSConnectionPool (object):
    """docstring for SNSConnectionPool"""
    def __init__(self, aws_access_key_id, aws_secret_access_key):
        super(SNSConnectionPool, self).__init__()
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.connections = {}
        self.applications = {}

    def get_connection(self, arn):
        if arn.service != "sns":
            raise ValueError("%s isn't sns arn", arn.arn_string)
        if arn.region not in self.connections:
            connection = boto.sns.connect_to_region(
                arn.region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key)
            self.connections[arn.region] = connection

        return self.connections[arn.region]

    def get_application(self, app_arn):
        if app_arn.arn_string not in self.applications:
            app_connection = self.get_connection(app_arn)
            app = APNApp(app_arn, app_connection)
            self.applications[app_arn.arn_string] = app

        return self.applications[app_arn.arn_string]


class APNApp():
    """docstring for APNApp"""
    def __init__(self, app_arn, connection):
        self.app_arn = app_arn
        self.connection = connection

    def send_aps_message(self, token, message):
        target_arn = self.get_arn_by_token(token)
        sns_message = {self.app_arn.platform: json.dumps(message)}
        response = self.connection.publish(
            message_structure="json", target_arn=target_arn, message=json.dumps(sns_message))

        if "PublishResponse" not in response:
            raise SNSResponseError("Wrong response format")

        response_body = response["PublishResponse"]

        if "PublishResult" not in response_body:
            raise SNSResponseError("Response without result")

        result = response_body["PublishResult"]

        if "MessageId" not in result:
            raise SNSResponseError("Message was not sent")

    @lru_cache(maxsize=1024)
    def get_arn_by_token(self, token):
        response = self.connection.create_platform_endpoint(
            platform_application_arn=self.app_arn.arn_string,
            token=token)

        if "CreatePlatformEndpointResponse" not in response:
            raise SNSResponseError("Wrong response format")

        response_body = response["CreatePlatformEndpointResponse"]

        if "CreatePlatformEndpointResult" not in response_body:
            raise SNSResponseError("No result in the response")

        response_result = response_body["CreatePlatformEndpointResult"]

        if "EndpointArn" not in response_result:
            raise SNSResponseError("No endpoint arn in the result")

        return response_result["EndpointArn"]


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='sns', description='Console sns client')

    aws_group = parser.add_argument_group('AWS parameters')
    aws_group.add_argument('--key-id', '-i', action='store', required=True, nargs='?',
                           help='AWS key id')
    aws_group.add_argument('--key-secret', '-s', action='store', required=True, nargs='?',
                           help='AWS key secret')

    sns_group = parser.add_argument_group('SNS parameters')
    sns_group.add_argument('--app-arn', '-a', action='store', required=True, nargs='?',
                           help='SNS Application ARN')

    aps_group = parser.add_argument_group('APS parameters')

    aps_group.add_argument('--token', '-t', action='store', required=True, nargs='?',
                           help='APS device push token')
    aps_group.add_argument('--message', '-m', action='store', required=True, nargs='?',
                           help='APS message')

    args = parser.parse_args()
    print args

    app_arn = SNSArn(args.app_arn)
    connection_pool = SNSConnectionPool(args.key_id, args.key_secret)
    app = connection_pool.get_application(app_arn)

    print("Message %s" % args.message)
    message_json = json.loads(args.message)
    if message_json is None:
        print("Can't parse message %s" % args.message)
        sys.exit(-1)

    app.send_aps_message(args.token, message_json)

if __name__ == "__main__":
    main()
