__author__ = 'v.kovtash@gmail.com'

from app_builder import make_app
import logging
import signal
import sys

def arguments():
    import argparse

    parser = argparse.ArgumentParser(prog='r2xserver',description='RESTFull XMPP client')
    parser.add_argument('--port','-p', action='store', default=5000, type=int, nargs='?',
        help='Server port number.')
    parser.add_argument('--address','-a', action='store', default='0.0.0.0', nargs='?',
        help='Server bind address.')
    parser.add_argument('--log-level', action='store', default='info', nargs='?',
        choices=['info','warning','error','debug'],
        help='Logging verbosity level.')
    push_settings_group = parser.add_argument_group('Push server settings')
    push_settings_group.add_argument('--push-mechanism', action='store', nargs='?',
        choices=['apnwsgi', 'pyapns'],
        help='Push mechanism.')
    push_settings_group.add_argument('--push-server-address', action='store', nargs='?',
        help='Push server address.')
    push_settings_group.add_argument('--push-app-id', action='store', default='im', nargs='?',
        help='Push application id.')
    push_settings_group.add_argument('--push-cert-dir', action='store', default='certificates', nargs='?',
        help='Push certificates directory. Program will search for certificate with name PUSH_APP_ID.pem')
    push_settings_group.add_argument('--push-dev-mode', action='store_true',
        help='Push notifications will be sent to development push server.')

    arguments = parser.parse_args()

    if arguments.push_mechanism is not None and arguments.push_server_address is None:
        print('--push-server-address parameter required when --push-mechanism parameter is set.')
        parser.print_help()
        sys.exit(1)

    return arguments

def set_logging_level(logging_level):
    if logging_level == 'warning':
        logging.basicConfig(level=logging.WARNING)
    elif logging_level == 'error':
        logging.basicConfig(level=logging.ERROR)
    elif logging_level == 'debug':
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


def main():
    args = arguments()
    print(args)
    set_logging_level(args.log_level)

    app = make_app(push_dev_mode=args.push_dev_mode,
        push_notification_sender=args.push_mechanism,
        push_server_address=args.push_server_address,
        push_app_id=args.push_app_id,
        push_cert_dir=args.push_cert_dir)

    def term_handler(signum = None, frame = None):
        logging.info('Application termination started')
        app.close()
        logging.info('Application terminated')
        sys.exit(0)

    signal.signal(signal.SIGTERM, term_handler)
    signal.signal(signal.SIGINT, term_handler)

    app.run(host=args.address, port=args.port, server='cherrypy')


if __name__ == '__main__':
    main()