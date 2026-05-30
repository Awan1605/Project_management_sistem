import json
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import WebPushSubscription, UserNotification, Task

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush, WebPushException
except Exception:  # pragma: no cover - optional dependency
    webpush = None
    WebPushException = Exception


def _is_webpush_configured():
    return bool(
        webpush and
        settings.WEBPUSH_VAPID_PUBLIC_KEY and
        settings.WEBPUSH_VAPID_PRIVATE_KEY
    )


def _notification_payload(notification):
    if not notification:
        return None
    title = notification.actor.username if notification.actor_id else 'Notification'
    body = notification.message or 'You have a new update.'
    url = '/'
    if notification.id:
        url = f'/notifications/{notification.id}/open/'
    icon = '/static/arva/img/default-favicon.png'
    return {
        'title': title,
        'body': body,
        'url': url,
        'icon': icon,
        'notification_id': notification.id,
        'notification_type': notification.notification_type,
        'task_id': notification.task_id,
        'comment_id': notification.comment_id,
    }


def send_push_for_notification(notification):
    if not _is_webpush_configured():
        return
    if not notification or not notification.recipient_id:
        return

    payload = _notification_payload(notification)
    if not payload:
        return

    subscriptions = WebPushSubscription.objects.filter(user_id=notification.recipient_id, is_active=True)
    if not subscriptions.exists():
        return

    data = json.dumps(payload)
    vapid_private_key = settings.WEBPUSH_VAPID_PRIVATE_KEY
    vapid_claims = {'sub': settings.WEBPUSH_VAPID_CLAIMS_SUBJECT}

    for subscription in subscriptions:
        subscription_info = {
            'endpoint': subscription.endpoint,
            'keys': {
                'p256dh': subscription.p256dh,
                'auth': subscription.auth,
            }
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=data,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status_code in (404, 410):
                subscription.is_active = False
                subscription.save(update_fields=['is_active', 'updated_at'])
            logger.warning('Web push send failed for subscription %s: %s', subscription.id, exc)
        except Exception as exc:  # pragma: no cover
            logger.warning('Unexpected web push error for subscription %s: %s', subscription.id, exc)


def send_due_soon_push_notifications(hours_ahead=24):
    """Push reminder for tasks due soon. Intended for cron/management command."""
    if not _is_webpush_configured():
        return 0

    now = timezone.now()
    upcoming = now + timedelta(hours=hours_ahead)
    tasks = Task.objects.filter(
        is_archived=False,
        due_date__isnull=False,
        due_date__gte=now.date(),
        due_date__lte=upcoming.date(),
    ).select_related('project').prefetch_related('assignees')

    sent = 0
    for task in tasks:
        for assignee in task.assignees.all():
            if not assignee.is_active:
                continue
            payload = {
                'title': 'Task deadline approaching',
                'body': f'Task "{task.title}" is due on {task.due_date.strftime("%d %b %Y")}.',
                'url': f'/task/{task.id}/',
                'icon': '/static/arva/img/default-favicon.png',
                'notification_type': 'TASK_DUE_SOON',
                'task_id': task.id,
            }
            data = json.dumps(payload)
            subs = WebPushSubscription.objects.filter(user=assignee, is_active=True)
            for sub in subs:
                try:
                    webpush(
                        subscription_info={
                            'endpoint': sub.endpoint,
                            'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                        },
                        data=data,
                        vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                        vapid_claims={'sub': settings.WEBPUSH_VAPID_CLAIMS_SUBJECT},
                    )
                    sent += 1
                except WebPushException as exc:
                    status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
                    if status_code in (404, 410):
                        sub.is_active = False
                        sub.save(update_fields=['is_active', 'updated_at'])
    return sent
