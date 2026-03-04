from datetime import timedelta
from django.utils.timezone import now
from threading import Thread
from django.core.mail import send_mail

def is_user_online(last_activity):
    if not last_activity:
        return False
    return (now() - last_activity) < timedelta(minutes=1)

class EmailThread(Thread):
    def __init__(self, subject, message, html_message, from_email, recipient_list):
        self.subject = subject
        self.message = message
        self.html_message = html_message
        self.from_email = from_email
        self.recipient_list = recipient_list
        Thread.__init__(self)

    def run(self):
        send_mail(
            subject=self.subject,
            message=self.message,
            html_message=self.html_message,
            from_email=self.from_email,
            recipient_list=self.recipient_list,
            fail_silently=True,
        )
