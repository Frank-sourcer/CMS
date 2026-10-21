import os
from dotenv import load_dotenv
from mpesakit import MpesaClient

load_dotenv()

mpesa_client = MpesaClient(
    consumer_key=os.getenv("MPESA_CONSUMER_KEY"),
    consumer_secret=os.getenv("MPESA_CONSUMER_SECRET"),
    environment=os.getenv("MPESA_ENVIRONMENT", "sandbox"),
)
