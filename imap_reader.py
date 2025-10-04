
from typing import List, Dict, Any
import imaplib, email, re
import pandas as pd

KEY_TERMS = [
    "catalog", "price", "pdf", "dealer", "distributor", "order",
    "import", "sample", "shipping", "freight", "quotation", "quote",
    "FOB", "CIF", "EXW", "DDP", "invoice", "proforma", "payment"
]

def fetch_important(host: str, port: int, username: str, password: str, mailbox: str="INBOX", limit: int=200) -> pd.DataFrame:
    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(username, password)
    imap.select(mailbox)
    status, data = imap.search(None, 'ALL')
    ids = data[0].split()[-limit:]
    rows=[]
    for i in ids[::-1]:
        res, msg_data = imap.fetch(i, "(RFC822)")
        if res != "OK": 
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subj = msg.get("Subject","")
        from_ = msg.get("From","")
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8","ignore")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8","ignore")
            except Exception:
                pass

        text = (subj + " " + body).lower()
        score = sum(1 for k in KEY_TERMS if k.lower() in text)
        if score >= 1:
            rows.append({"From": from_, "Subject": subj, "Score": score})
    imap.close(); imap.logout()
    return pd.DataFrame(rows)
