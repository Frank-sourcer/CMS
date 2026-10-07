from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Hub
from ..hub_schemas import HubCreate, HubUpdate, HubResponse
from ..security import get_current_user, require_role


router = APIRouter(
    prefix="/hubs",
    tags=["Hubs"]
)


@router.get("/", response_model=list[HubResponse])
def get_hubs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return db.query(Hub).all()


@router.post(
    "/",
    response_model=HubResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hub(
    payload: HubCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    existing = db.query(Hub).filter(
        (Hub.name == payload.name) | (Hub.code == payload.code)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hub with this name or code already exists",
        )

    hub = Hub(
        name=payload.name,
        code=payload.code,
        location=payload.location,
    )
    db.add(hub)

    try:
        db.commit()
        db.refresh(hub)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hub with this name or code already exists",
        )

    return hub


@router.get("/{hub_id}", response_model=HubResponse)
def get_hub(
    hub_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    hub = db.query(Hub).filter(Hub.id == hub_id).first()
    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub not found",
        )
    return hub


@router.patch("/{hub_id}", response_model=HubResponse)
def update_hub(
    hub_id: int,
    payload: HubUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    hub = db.query(Hub).filter(Hub.id == hub_id).first()
    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hub, field, value)

    try:
        db.commit()
        db.refresh(hub)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hub with this name or code already exists",
        )

    return hub
