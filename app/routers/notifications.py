from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models import NotificationLog
from ..notification_schemas import (
    NotificationLogResponse,
    NotificationStatusUpdate,
    NotificationStatus,
)
from ..pagination import PaginatedResponse
from ..security import get_current_user, require_role


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


@router.get("/", response_model=PaginatedResponse[NotificationLogResponse])
def get_notifications(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    if limit > 100:
        limit = 100

    total = db.query(NotificationLog).count()
    notifications = (
        db.query(NotificationLog)
        .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "items": notifications,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(notifications) < total,
    }

@router.get("/{notification_id}", response_model=NotificationLogResponse)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    notification = db.query(NotificationLog).filter(
        NotificationLog.id == notification_id
    ).first()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return notification


@router.patch("/{notification_id}", response_model=NotificationLogResponse)
def update_notification_status(
    notification_id: int,
    payload: NotificationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    notification = db.query(NotificationLog).filter(
        NotificationLog.id == notification_id
    ).first()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if notification.status == NotificationStatus.SENT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update a notification that has already been sent",
        )

    notification.status = payload.status.value

    if payload.status == NotificationStatus.SENT:
        notification.sent_at = utcnow()
        notification.error = None
    elif payload.status == NotificationStatus.FAILED:
        notification.error = payload.error or "Unknown error"

    db.commit()
    db.refresh(notification)
    return notification


def deliver_notification(db, notif):
    """Send a queued notification via SMS. Updates status and returns the row."""
    from ..sms import send_sms
    from ..database import utcnow

    result = send_sms(notif.recipient, notif.message)

    if result.get("ok"):
        recipients = result.get("response", {}).get("SMSMessageData", {}).get("Recipients", [])
        if recipients and recipients[0].get("status") == "Success":
            notif.status = "sent"
            notif.sent_at = utcnow()
            notif.error = None
        else:
            notif.status = "failed"
            notif.error = str(recipients)
    else:
        notif.status = "failed"
        notif.error = result.get("error", "unknown")

    db.commit()
    db.refresh(notif)
    return notif
