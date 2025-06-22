import os
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# Discord needs to verify bot application.
def verify_signature(event):
    raw_body = event["rawBody"]
    verify_key = VerifyKey(bytes.fromhex(os.environ["PUBLIC_KEY"]))
    auth_sig = event["params"]["header"].get("x-signature-ed25519")
    auth_ts  = event["params"]["header"].get("x-signature-timestamp")

    try:
        verify_key.verify(f"{auth_ts}{raw_body}".encode(), bytes.fromhex(auth_sig))
    except BadSignatureError:
        raise Exception("Verification failed")


# Discord uses "ping pong" message to verify bot.
def is_ping_pong(body: dict) -> bool:
    if body["type"]:
        if body["type"] == 1:
            return True
    return False
