# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

from xmpp_session_pool import BaseNotificator
from Queue import Queue
import threading
import sns_sender
import logging
from boto.exception import BotoServerError

logger = logging.getLogger('SNSNotificator')

class SNSNotificator(threading.Thread, BaseNotificator):
    def __init__(self, app_arn_string, aws_access_key_id, aws_secret_access_key):
        super(SNSNotificator, self).__init__()
        self.notifications = Queue()
        self.app_arn = sns_sender.SNSArn(app_arn_string)
        self.sns_sender = sns_sender.SNSConnectionPool(aws_access_key_id, aws_secret_access_key)

    def run(self):
        logger.info('Started')
        while True:
            notification_task = self.notifications.get()
            self.notifications.task_done()

            if notification_task is None:
                logger.debug('Empty task, finishing processing')
                break

            token = notification_task['token']
            message = notification_task['message']

            try:
                sns_app = self.sns_sender.get_application(self.app_arn)
            except BotoServerError as exception:
                logger.error("SNS server error")
                logger.error("Push notification for %s was not sent" % token)
                logger.exception(exception.value)

            try:
                sns_app.send_aps_message(token, message)
                logger.debug('Push sent for %s' % token)
            except sns_sender.SNSResponseError as exception:
                logger.error("Push notification for %s was not sent" % token)
                logger.exception("Response error", exception.value)
            except BotoServerError as exception:
                if exception.error_code == "EndpointDisabled":
                    sns_app.enable_endpoint(token)
                    self.notifications.put({'token': token, 'message': message})
                else:
                    logger.error("SNS server error")
                    logger.error("Push notification for %s was not sent" % token)
                    logger.exception(exception)
            except Exception as exception:
                logger.error("Unknown error while sending push notification")
                logger.error("Push notification for %s was not sent" % token)
                logger.exception(exception)

        logger.info('Thread finished')

    def stop(self):
        logger.info('Stopping')
        self.notifications.put(None)

    def perform_notification(self, token, aps_message):
        self.notifications.put({'token': token, 'message': aps_message})
