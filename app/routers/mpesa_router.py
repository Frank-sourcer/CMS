import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models import Shipment, Payment
from ..security import require_role
from ..mpesa import get_mpesa_client
from mpesakit.mpesa_express import TransactionType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["M-Pesa"])


@router.post("/shipments/{shipment_id}/pay-mpesa")
async def initiate_mpesa_payment(
    shipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher", "rider")),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")

    # Optional phone override from JSON body: {"phone": "+254..."}
    try:
        body = await request.json()
        request_phone = body.get("phone") if isinstance(body, dict) else None
    except Exception:
        request_phone = None

    raw_phone = request_phone or shipment.recipient_phone
    if not raw_phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No phone available — provide 'phone' in body or set shipment.recipient_phone",
        )

    phone = raw_phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]

    pending = (
        db.query(Payment)
        .filter(
            Payment.shipment_id == shipment_id,
            Payment.method == "cod",
            Payment.status == "pending",
        )
        .first()
    )
    if pending is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No pending COD payment for this shipment",
        )

    shortcode = int(os.getenv("MPESA_SHORTCODE", "174379"))
    client = get_mpesa_client()

    try:
        response = client.stk_push(
            business_short_code=shortcode,
            passkey=os.getenv("MPESA_PASSKEY"),
            transaction_type=TransactionType.CUSTOMER_PAYBILL_ONLINE,
            amount=int(pending.amount),
            party_a=phone,
            party_b=str(shortcode),
            phone_number=phone,
            callback_url=os.getenv("MPESA_CALLBACK_URL"),
            account_reference=shipment.tracking_number[:12],
            transaction_desc="Delivery",
        )
    except Exception as exc:
        logger.exception("M-Pesa STK push failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"M-Pesa request failed: {exc}",
        )

    checkout_id = getattr(response, "CheckoutRequestID", None)
    if checkout_id:
        pending.reference = checkout_id
        db.commit()

    return {
        "message": "STK push sent",
        "phone": phone,
        "checkout_request_id": checkout_id,
        "customer_message": getattr(response, "CustomerMessage", "Check your phone"),
    }


@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    logger.info("M-Pesa callback received: %s", payload)

    try:
        stk = payload["Body"]["stkCallback"]
        result_code = stk.get("ResultCode")
        checkout_id = stk.get("CheckoutRequestID")

        if result_code == 0:
            items = stk.get("CallbackMetadata", {}).get("Item", [])
            receipt = next(
                (i["Value"] for i in items if i["Name"] == "MpesaReceiptNumber"), None
            )
            payment = (
                db.query(Payment)
                .filter(Payment.reference == checkout_id)
                .first()
            )
            if payment:
                payment.status = "paid"
                payment.reference = receipt or checkout_id
                payment.collected_at = utcnow()
                db.commit()
                logger.info("Payment %s marked paid (receipt=%s)", payment.id, receipt)
        else:
            logger.warning(
                "STK push failed/cancelled: code=%s desc=%s",
                result_code, stk.get("ResultDesc"),
            )
    except (KeyError, TypeError) as exc:
        logger.exception("Could not parse M-Pesa callback: %s", exc)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
