from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NotificationLog
from ..notification_schemas import (
    NotificationLogResponse,
    NotificationStatusUpdate,
    NotificationStatus,
)
from ..security import get_current_user, require_role


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


@router.get("/", response_model=list[NotificationLogResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    return (
        db.query(NotificationLog)
        .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
        .all()
    )


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
        notification.sent_at = datetime.utcnow()
        notification.error = None
    elif payload.status == NotificationStatus.FAILED:
        notification.error = payload.error or "Unknown error"

    db.commit()
    db.refresh(notification)
    return notification
