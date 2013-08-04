__author__ = 'v.kovtash@gmail.com'

from r2x_bottle_app import BottleApp
from r2x_tornado_app import TornadoApp
import logging
import logging.handlers
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
    parser.add_argument('--log-file', action='store', nargs='?',
        help='Log file path.')
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

def set_logging_config(logging_level_string = 'info',
                       logging_format = '%(asctime)s %(levelname)s %(message)s',
                       log_file = None):
    formatter = logging.Formatter(logging_format)
    level = getattr(logging, logging_level_string.upper(), logging.INFO)
    logging.basicConfig(format=logging_format,level=level)
    root_logger = logging.getLogger('')

    if  log_file is not None:
        file_handler = logging.handlers.TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=7)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

def main():
    args = arguments()
    set_logging_config(logging_level_string = args.log_level, log_file = args.log_file)

    app = TornadoApp(push_dev_mode=args.push_dev_mode,
        push_notification_sender=args.push_mechanism,
        push_server_address=args.push_server_address,
        push_app_id=args.push_app_id,
        push_cert_dir=args.push_cert_dir)

    def term_handler(signum = None, frame = None):
        logging.info('Server cleanup started')
        app.stop()
        logging.info('Server shuts down')
        sys.exit(0)

    signal.signal(signal.SIGTERM, term_handler)
    signal.signal(signal.SIGINT, term_handler)

    logging.info('Starting server at address %s:%s',args.address,args.port)
    app.run(host=args.address, port=args.port)


if __name__ == '__main__':
    main()