from html.parser import HTMLParser
from io import StringIO
import email
import imaplib


def set_credentials(username, password) -> bool:
    """Check IMAP credentials by attempting a login."""
    try:
        imap_server = 'imap.gmail.com'
        imap_port = 993
        conn = imaplib.IMAP4_SSL(imap_server, imap_port)
        conn.login(username, password)
        try:
            conn.logout()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _search_ids(conn, *criteria):
    """Helper to run a search and return a list of ids (as strings)."""
    typ, data = conn.search(None, *criteria)
    if typ != 'OK' or not data or not data[0]:
        return []
    return data[0].decode().split()


def fetch_emails_from_imap(username, password):
    """Return a list of email IDs (newest first).

    We try Primary/UNSEEN first, then INBOX/UNSEEN, and if none found, fall back
    to ALL in INBOX so the UI always has something to render for testing.
    """
    imap_server = 'imap.gmail.com'
    imap_port = 993
    conn = imaplib.IMAP4_SSL(imap_server, imap_port)
    conn.login(username, password)

    # Always select INBOX read-only
    conn.select('INBOX', readonly=True)

    # Gmail-specific raw query for Primary category + UNSEEN
    ids = _search_ids(conn, 'X-GM-RAW', 'Category:Primary', 'UNSEEN')
    if not ids:
        # Fallback: any UNSEEN in INBOX
        ids = _search_ids(conn, 'UNSEEN')
    if not ids:
        # Last resort: ALL (so user can test even with no unread)
        ids = _search_ids(conn, 'ALL')

    # Newest first for nicer UX
    ids.reverse()

    try:
        conn.close()
    except Exception:
        pass
    try:
        conn.logout()
    except Exception:
        pass

    return ids


def decode_emails(email_ids, start_index, end_index, username, password):
    imap_server = 'imap.gmail.com'
    imap_port = 993

    conn = imaplib.IMAP4_SSL(imap_server, imap_port)
    conn.login(username, password)
    conn.select('INBOX', readonly=True)

    messages = []

    for eid in email_ids[start_index:end_index]:
        try:
            typ, data = conn.fetch(eid, '(RFC822)') #(RFC822) means "fetch the full raw email source".
            if typ != 'OK' or not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = msg.get('subject') or ''
            sender = msg.get('from') or ''
            message_id = msg.get('Message-ID', '')
            in_reply_to = msg.get('In-Reply-To', '')

            content = ''
            attachments = []

            if msg.is_multipart():
                # Prefer text/plain; if not found, fall back to text/html (stripped)
                plain_found = False
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = (part.get_content_disposition() or '').lower()

                    if disp == 'attachment':
                        fname = part.get_filename()
                        if fname:
                            attachments.append(fname)
                        continue

                    if ctype == 'text/plain' and not plain_found:
                        try:
                            content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                            plain_found = True
                        except Exception:
                            pass

                if not plain_found:
                    # try html body
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        disp = (part.get_content_disposition() or '').lower()
                        if disp == 'attachment':
                            continue
                        if ctype == 'text/html':
                            try:
                                html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                content = strip_tags(html)
                                break
                            except Exception:
                                pass
            else:
                try:
                    payload = msg.get_payload(decode=True) or b''
                    content = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                except Exception:
                    content = ''

            messages.append({
                'Message ID': message_id,
                'from': sender,
                'subject': subject,
                'content': content,
                'IsReply': bool(in_reply_to),
                'InReplyTo': in_reply_to,
                'StoreReplyThread': [],
                'attachment': attachments,
            })
        except Exception:
            # skip bad emails instead of breaking the whole page
            continue

    try:
        conn.close()
    except Exception:
        pass
    try:
        conn.logout()
    except Exception:
        pass

    return messages


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self._buf = StringIO()

    def handle_data(self, d):
        self._buf.write(d)

    def get_data(self):
        return self._buf.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html or '')
    return s.get_data()