from django.core.management.base import BaseCommand

from arva.push import send_due_soon_push_notifications


class Command(BaseCommand):
    help = 'Send browser push reminders for tasks with approaching deadlines.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Lookahead window in hours (default: 24)')

    def handle(self, *args, **options):
        hours = max(1, int(options.get('hours') or 24))
        sent = send_due_soon_push_notifications(hours_ahead=hours)
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} due-soon push notifications.'))

