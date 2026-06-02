from uuid import UUID


from app.api.models.emails import Email
from app.api.schemas.emails import EmailInDB
from app.api.repo.email_repo import EmailRepository


class EmailService:
    def __init__(self, email_repo: EmailRepository):
        self._email_repo = email_repo

    def get_proccessed_emails(self, email_id: UUID) -> Email | None:
        email: Email | None = self._email_repo._get_records(email_id=email_id)
        return email

    def get_proccessed_email(self, email_id: UUID) -> Email | None:
        email: Email | None = self._email_repo.get_record(email_id=email_id)
        return email

    def create_email(self, email_payload: EmailInDB):
        self._email_repo.add(entity=email_payload)
        self._email_repo.commit()

    def update_processed_emails(self, email: Email):
        self._email_repo.add(model=email)
        self._email_repo.commit()
