"""SMTP approuvé : enveloppe explicite, identifiant persistant, aucune reprise automatique.
Accepté SMTP ne signifie pas reçu/lu. Une coupure après DATA est incertaine.
"""
from __future__ import annotations
import ipaddress
import os
import smtplib
import ssl
from collections.abc import Mapping
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


class MailError(Exception):
    def __init__(self, message: str, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


def mailbox(value: str) -> str:
    """Une adresse brute : ni liste, ni nom affiché, ni injection d'en-tête."""
    if not isinstance(value, str) or any(c in value for c in '\r\n,;<>'):
        raise MailError('adresse invalide : une seule boîte autorisée')
    try:
        parsed = Address(addr_spec=value)
    except (ValueError, IndexError) as exc:
        raise MailError('adresse courriel invalide') from exc
    if not parsed.username or not parsed.domain or parsed.addr_spec != value:
        raise MailError('adresse courriel invalide')
    return value


class Mailer:
    def __init__(self, host: str, port: int = 587, user: str = '', password: str = '',
                 sender: str = '', starttls: bool = True, timeout_s: float = 15.0):
        self.host, self.port, self.user = host, int(port), user
        self._password, self.sender = password, sender or user
        self.starttls, self.timeout = starttls, timeout_s
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host == 'localhost'
        if not starttls and self.port != 465 and (not local or user or password):
            raise ValueError('SMTP distant/authentifié sans TLS interdit')

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> 'Mailer | None':
        env = os.environ if env is None else env
        host = env.get('ARPAGONA_SMTP_HOST', '').strip()
        if not host:
            return None
        password = env.get('ARPAGONA_SMTP_PASSWORD', '')
        path = env.get('ARPAGONA_SMTP_PASSWORD_FILE', '').strip()
        if not password and path:
            password = Path(path).read_text(encoding='utf-8').strip()
        return cls(host, int(env.get('ARPAGONA_SMTP_PORT', '587')),
                   env.get('ARPAGONA_SMTP_USER', ''), password,
                   env.get('ARPAGONA_SMTP_FROM', '') or env.get('ARPAGONA_SMTP_USER', ''),
                   env.get('ARPAGONA_SMTP_STARTTLS', '1') != '0')

    def __repr__(self):
        return f'Mailer(host={self.host!r}, port={self.port}, sender={self.sender!r})'

    def send(self, to: str, subject: str, body: str, message_id: str | None = None) -> str:
        mailbox(to)
        mailbox(self.sender)
        if not isinstance(subject, str) or not subject or any(c in subject for c in '\r\n'):
            raise MailError('objet invalide')
        if not isinstance(body, str):
            raise MailError('corps invalide')
        msg = EmailMessage()
        msg['From'], msg['To'], msg['Subject'] = self.sender, to, subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = message_id or make_msgid(domain='arpagona.com')
        msg.set_content(body)
        smtp = None
        submitted = False
        try:
            if self.port == 465:
                smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout,
                                       context=ssl.create_default_context())
            else:
                smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
            if self.user:
                smtp.login(self.user, self._password)
            submitted = True
            smtp.send_message(msg, from_addr=self.sender, to_addrs=[to])
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
            raise MailError(f'refus SMTP explicite ({type(exc).__name__})') from exc
        except (smtplib.SMTPException, OSError) as exc:
            message = 'remise incertaine : vérifier avant toute nouvelle tentative' if submitted else 'connexion SMTP échouée avant remise'
            raise MailError(message, uncertain=submitted) from exc
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except (OSError, smtplib.SMTPException):
                    smtp.close()  # QUIT échoué ne transforme pas DATA accepté en échec.
        return str(msg['Message-ID'])
