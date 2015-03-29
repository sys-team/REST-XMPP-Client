#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

from r2x_tornado_app import TornadoApp
from xmpp_session_pool import digest
from push_notificators import PyAPNSNotificator, SNSNotificator
import uuid
import logging
import logging.handlers
import signal
import sys


def arguments():
    import argparse

    parser = argparse.ArgumentParser(prog='r2xserver', description='RESTFull XMPP client')
    parser.add_argument('--port', '-p', action='store', default=5000, type=int,
                        nargs='?', help='Server port number.')
    parser.add_argument('--address', '-a', action='store', default='0.0.0.0', nargs='?',
                        help='Server bind address.')
    parser.add_argument('--log-level', action='store', default='info', nargs='?',
                        choices=['info', 'warning', 'error', 'debug'],
                        help='Logging verbosity level.')
    parser.add_argument('--log-file', action='store', nargs='?',
                        help='Log file path.')
    parser.add_argument('--push-mechanism', action='store', nargs='?',
                        choices=['pyapns', 'aws'],
                        help='Push mechanism.')

    pyapns = parser.add_argument_group('PyAPNS server settings')
    pyapns.add_argument('--pyapns-host', action='store', nargs='?', help='PyAPNS server address.')
    pyapns.add_argument('--pyapns-cert-path', action='store', nargs='?',
                        help='Push certificate file path.')
    pyapns.add_argument('--pyapns-app-id', action='store', default='r2xserver', nargs='?',
                        help='PyAPNS application id.')
    pyapns.add_argument('--pyapns-dev-mode', action='store_true',
                        help='Push notifications will be sentto sandbox apn server.')

    sns = parser.add_argument_group('SNS settings')
    sns.add_argument('--aws-sns-arn', action='store', nargs='?', help='SNS App ARN')
    sns.add_argument('--aws-key-id', action='store', nargs='?',
                        help='AWS key id')
    sns.add_argument('--aws-key-secret', action='store', default='r2xserver', nargs='?',
                        help='AWS key secret')

    admin_token = parser.add_argument_group('Admin token')
    admin_token.add_argument('--admin-token-enc', action='store', nargs='?',
                             help='Admin token encoden with SHA1.')
    admin_token.add_argument('--admin-token-plain', action='store', nargs='?',
                             help='Plain text admin token.')

    return parser.parse_args()


def set_logging_config(logging_level_string='info',
                       logging_format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                       log_file=None):
    formatter = logging.Formatter(logging_format)
    level = getattr(logging, logging_level_string.upper(), logging.INFO)
    logging.basicConfig(format=logging_format, level=level)
    root_logger = logging.getLogger('')

    if log_file is not None:
        file_handler = logging.handlers.TimedRotatingFileHandler(log_file, when='midnight',
                                                                 interval=1, backupCount=7)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


logger = logging.getLogger('R2XServer')

def main():
    args = arguments()
    set_logging_config(logging_level_string=args.log_level, log_file=args.log_file)

    push_sender = None

    if args.push_mechanism == "pyapns":
        push_sender = PyAPNSNotificator(host=args.pyapns_host, app_id=args.pyapns_app_id,
                                        cert_file=args.pyapns_cert_path,
                                        dev_mode=args.pyapns_dev_mode)
    elif args.push_mechanism == "aws":
        push_sender = SNSNotificator(app_arn_string = args.aws_sns_arn, 
                                     aws_access_key_id = args.aws_key_id, 
                                     aws_secret_access_key = args.aws_key_secret)

    admin_token_hash = None

    if args.admin_token_enc is not None:
        if len(args.admin_token_enc) != digest.hex_digest_size():
            sys.exit('Encrypted token must be a hexadecimal string %s characters length' %
                     digest.hex_digest_size())
        admin_token_hash = args.admin_token_enc
    elif args.admin_token_plain is not None:
        admin_token_hash = digest.digest(args.admin_token_plain)
    else:
        admin_token_hash = digest.digest(uuid.uuid4().hex)

    app = TornadoApp(push_sender=push_sender, admin_token_hash=admin_token_hash)

    def term_handler(signum=None, frame=None):
        logger.info('Server cleanup started')
        app.stop()
        logger.info('Server shuts down')
        sys.exit(0)

    signal.signal(signal.SIGTERM, term_handler)
    signal.signal(signal.SIGINT, term_handler)

    logger.info('Starting server at address %s %s', args.address, args.port)
    if admin_token_hash is not None:
        logger.info('Admin token hash %s', admin_token_hash)

    app.run(address=args.address, port=args.port)


if __name__ == '__main__':
    main()
