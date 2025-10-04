
from typing import List, Dict, Any
import smtplib, ssl, email.utils, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_smtp(
    host: str, port: int, username: str, password: str,
    from_name: str, from_email: str,
    to_email: str, subject: str,
    body_html: str=None, body_text: str=None, use_tls: bool=True
):
    """
    SMTP ile email gönderir. Gelişmiş hata yönetimi ile.
    """
    try:
        # Host adresini kontrol et
        if not host or not host.strip():
            raise ValueError("SMTP host adresi boş olamaz")
        
        # Host adresini temizle
        host = host.strip()
        
        # DNS çözümlemesi yap
        try:
            socket.gethostbyname(host)
        except socket.gaierror as e:
            raise ConnectionError(f"SMTP host adresi çözümlenemedi: {host}. Hata: {str(e)}")
        
        # Email mesajını oluştur
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        
        # İçerik ekle
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        
        # SSL context oluştur
        ctx = ssl.create_default_context()
        
        # SMTP bağlantısı kur ve email gönder
        if use_tls:
            logger.info(f"SMTP TLS bağlantısı kuruluyor: {host}:{port}")
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=ctx)
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
                logger.info(f"Email başarıyla gönderildi: {to_email}")
        else:
            logger.info(f"SMTP SSL bağlantısı kuruluyor: {host}:{port}")
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as server:
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
                logger.info(f"Email başarıyla gönderildi: {to_email}")
                
    except socket.gaierror as e:
        error_msg = f"DNS çözümleme hatası: {str(e)}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP kimlik doğrulama hatası: {str(e)}"
        logger.error(error_msg)
        raise AuthenticationError(error_msg)
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Alıcı email adresi reddedildi: {to_email}. Hata: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except smtplib.SMTPServerDisconnected as e:
        error_msg = f"SMTP sunucusu bağlantısı kesildi: {str(e)}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except smtplib.SMTPException as e:
        error_msg = f"SMTP hatası: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Beklenmeyen hata: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

class AuthenticationError(Exception):
    """SMTP kimlik doğrulama hatası"""
    pass
