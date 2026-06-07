import httpx
import resend
import secrets
from uuid import UUID, uuid4
from resend.exceptions import ApplicationError
from datetime import datetime, timezone, timedelta, date


from app.api.models.emails import Email
from app.api.schemas.auth import OtpInDB
from app.core.config import get_settings
from app.task.celery_app import celery_app
from app.api.schemas.emails import EmailInDB
from app.api.repo.otp_repo import OtpRepository
from app.api.schemas.analytics import UrlStatInDB
from app.api.repo.user_repo import UserRepository
from app.api.repo.redis_repo import RedisRepository
from app.api.repo.email_repo import EmailRepository
from app.api.services.otp_service import OtpService
from app.api.services.user_service import UserService
from app.api.services.email_service import EmailService
from app.task.db import get_db_session, get_redis_client
from app.api.repo.analytics_repo import AnalyticsRepository
from app.api.services.analytics_service import AnalyticsService


def get_email_service() -> EmailService:
    session = get_db_session()

    email_service: EmailService = EmailService(
        email_repo=EmailRepository(sync_session=session)
    )

    return email_service


def get_user_service() -> UserService:
    session = get_db_session()
    user_service: UserService = UserService(
        user_repo=UserRepository(sync_session=session)
    )
    return user_service


def get_otp_service() -> OtpService:
    session = get_db_session()
    otp_service: OtpService = OtpService(otp_repo=OtpRepository(sync_session=session))
    return otp_service


def get_analytics_service() -> AnalyticsService:
    session = get_db_session()
    redis_client = get_redis_client()
    analytics_service: AnalyticsService = AnalyticsService(
        analytics_repo=AnalyticsRepository(sync_session=session),
        redis_repo=RedisRepository(sync_redis=redis_client),
    )
    return analytics_service


def verification_message(otp: str):
    return f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                </head>
                <body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,sans-serif;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
                    <tr>
                        <td align="center">
                        <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;padding:40px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                            <tr>
                            <td align="center" style="padding-bottom:24px;">
                                <h2 style="margin:0;color:#1a1a1a;font-size:22px;">Verify your email</h2>
                            </td>
                            </tr>
                            <tr>
                            <td align="center" style="padding-bottom:16px;">
                                <p style="margin:0;color:#555555;font-size:15px;line-height:1.6;">
                                Use the code below to complete your verification. It expires in <strong>5 minutes</strong>.
                                </p>
                            </td>
                            </tr>
                            <tr>
                            <td align="center" style="padding:24px 0;">
                                <div style="display:inline-block;background:#f0f4ff;border-radius:8px;padding:16px 40px;">
                                <span style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#3b5bdb;">{otp}</span>
                                </div>
                            </td>
                            </tr>
                            <tr>
                            <td align="center" style="padding-top:16px;">
                                <p style="margin:0;color:#999999;font-size:13px;">
                                If you did not request this, please ignore this email.
                                </p>
                            </td>
                            </tr>
                        </table>
                        </td>
                    </tr>
                    </table>
                </body>
            </html>
            """


def reminder_message():
    return ""


class BaseTaskWithFailure(celery_app.Task):
    # errors to retry for
    autoretry_for = (
        httpx.TimeoutException,
        httpx.ConnectError,
        ConnectionError,
        ApplicationError,
    )

    # maximum retry value
    max_retries = 5

    """
    retry jitter set to True to ensure randomness in retry_backoff value
    this prevents overwhelming when multiple tasks fails simultaneously,
    retrying each task at different time
    """
    retry_jitter = True

    """
    increment retry delay value exponentially
    """
    retry_backoff = 2

    """
    maximum retry backoff - one minute
    """
    retry_backoff_max = 600


@celery_app.task(base=BaseTaskWithFailure)
def send_verification_email(
    email_id: UUID, recipient_email: str, user_id: str, purpose: str
):
    try:
        email_id: UUID = UUID(email_id)
        email_service = get_email_service()

        otp_service = get_otp_service()

        email: str = ""
        proccessed_email: Email | None = email_service.get_proccessed_email(email_id)

        if proccessed_email:
            email: str = proccessed_email.processed_emails.get("emails")[0]

        if not proccessed_email or email != recipient_email:
            otp: str = secrets.token_urlsafe(25)
            resend.api_key = get_settings().API_EMAIL

            resend.Emails.send(
                {
                    "from": get_settings().API_EMAIL,
                    "to": recipient_email,
                    "subject": "Email Verification Code",
                    "html": verification_message(otp),
                }
            )

            otp_payload: OtpInDB = OtpInDB(
                otp=otp,
                user_id=UUID(user_id),
                purpose=purpose,
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=get_settings().OTP_EXPIRE_TIME),
            )

            email_payload: EmailInDB = EmailInDB(
                id=email_id, processed_emails={"emails": [recipient_email]}
            )

            otp_service.create_otp(otp_payload)
            email_service.create_email(email_payload)
    finally:
        otp_service._otp_repo.close()
        email_service._email_repo.close()


@celery_app.task(base=BaseTaskWithFailure)
def send_reminder_email(email_id: UUID = uuid4()):
    try:
        user_service = get_user_service()
        email_service = get_email_service()

        deactivated_emails = user_service.get_deactivated_users()

        processed_emails: Email | None = email_service.get_proccessed_emails(email_id)

        if processed_emails:
            recipient_emails = processed_emails.processed_emails.get("emails")
        else:
            recipient_emails = []
            email_payload: EmailInDB = EmailInDB(
                id=email_id, processed_emails=processed_emails
            )

        emails: list[str] = list(set(deactivated_emails).difference(set(recipient_emails)))

        for email in emails:
            resend.api_key = get_settings().API_EMAIL

            resend.Emails.send(
                {
                    "from": get_settings().API_EMAIL,
                    "to": email,
                    "subject": "Deactivation Reminder",
                    "html": reminder_message(),
                }
            )

            recipient_emails.append(email)

            if processed_emails:
                processed_emails.processed_emails.update({"emails": recipient_emails})
                email_service.update_processed_emails(processed_emails)
            else:
                email_payload.processed_emails = recipient_emails
                email_service.create_email(email_payload)
    finally:
        user_service._user_repo.close()
        email_service._email_repo.close()


@celery_app.task(base=BaseTaskWithFailure)
def flush_clicks():
    try:
        analytics_service = get_analytics_service()

        keys: list[str] = analytics_service.get_clicks_keys("clicks:*")

        for key in keys:
            _, url_id, click_date = key.split(":")
            click_date = date.fromisoformat(click_date)
            clicks: int = int(analytics_service.get_clicks(key))

            url_stat: UrlStatInDB = UrlStatInDB(url_id=url_id, clicks=clicks, date=click_date)
            analytics_service.upsert_click(url_stat)
    finally:
        analytics_service._analytics_repo.close()
        analytics_service._redis_repo._sync_redis.close()


@celery_app.task(base=BaseTaskWithFailure)
def delete_deactivated_users():
    try:
        user_service = get_user_service()
        user_service.delete_deactivated_users()
    finally:
        user_service._user_repo.close()
