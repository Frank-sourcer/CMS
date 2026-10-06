from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Customer
from ..customer_schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
)
from ..shipment_schemas import ShipmentResponse
from ..security import (
    hash_password,
    get_current_user,
    require_role,
)


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


def customer_to_response(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "user_id": customer.user_id,
        "name": customer.user.name,
        "email": customer.user.email,
        "phone": customer.user.phone,
        "customer_type": customer.customer_type,
        "company_name": customer.company_name,
        "address": customer.address,
        "created_at": customer.created_at,
    }


@router.get("/", response_model=list[CustomerResponse])
def get_customers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return [customer_to_response(c) for c in db.query(Customer).all()]


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    if db.query(User).filter(User.email == customer.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Password is optional: admin/dispatcher may create walk-in
    # customers who don't need a login. Generate a random one.
    import secrets
    pwd = customer.password or secrets.token_urlsafe(16)

    new_user = User(
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        password_hash=hash_password(pwd),
        role="customer",
    )
    db.add(new_user)
    db.flush()   # assigns new_user.id without committing

    new_customer = Customer(
        user_id=new_user.id,
        customer_type=customer.customer_type,
        company_name=customer.company_name,
        address=customer.address,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    return customer_to_response(new_customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    customer = db.query(Customer).filter(
        Customer.id == customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return customer_to_response(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    customer = db.query(Customer).filter(
        Customer.id == customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return customer_to_response(customer)


@router.get(
    "/{customer_id}/shipments",
    response_model=list[ShipmentResponse],
)
def get_customer_shipments(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    customer = db.query(Customer).filter(
        Customer.id == customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return customer.shipments
