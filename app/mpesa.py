import os
from dotenv import load_dotenv
from mpesakit import MpesaClient

load_dotenv()

_client = None


def get_mpesa_client() -> MpesaClient:
    """Lazy singleton — only builds the client when actually needed."""
    global _client
    if _client is None:
        consumer_key = os.getenv("MPESA_CONSUMER_KEY")
        consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
        environment = os.getenv("MPESA_ENVIRONMENT", "sandbox")

        if not consumer_key or not consumer_secret:
            raise RuntimeError(
                "MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET must be set "
                "in .env or the environment."
            )

        _client = MpesaClient(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            environment=environment,
        )
    return _client
