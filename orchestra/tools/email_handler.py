"""
OrchestraAI — Email Handler (Outlook COM Automation)
======================================================
Automates Microsoft Outlook via win32com for drafting, sending,
and reading emails. Fully local — no cloud email APIs needed.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("orchestra.email")


def _get_outlook():
    """Get or create an Outlook COM application instance."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        return outlook
    except Exception as e:
        logger.error(f"Could not connect to Outlook: {e}")
        raise RuntimeError(
            "Microsoft Outlook is not installed or not running. "
            "Please open Outlook first."
        ) from e


def _mailto_fallback(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> Dict[str, Any]:
    """Fallback to system default email client using mailto link when COM fails."""
    import urllib.parse
    import webbrowser
    query = {}
    if subject:
        query["subject"] = subject
    if body:
        query["body"] = body
    if cc:
        query["cc"] = cc
    if bcc:
        query["bcc"] = bcc
    
    query_str = urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    mailto_url = f"mailto:{to}"
    if query_str:
        mailto_url += f"?{query_str}"
        
    try:
        webbrowser.open(mailto_url)
        return {
            "success": True,
            "action": "mailto_fallback",
            "to": to,
            "subject": subject,
            "details": "Outlook COM interface not registered and SMTP is not configured in your .env file. Opened the draft in your default email client. To send emails completely in the background, configure SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, and SMTP_PASSWORD in your .env file."
        }
    except Exception as err:
        return {
            "success": False,
            "error": f"Outlook COM not registered, and mailto fallback failed: {str(err)}"
        }


def draft_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> Dict[str, Any]:
    """
    Create a draft email in Outlook without sending it.
    
    Args:
        to: Recipient email address(es), separated by semicolons.
        subject: Email subject line.
        body: Email body text.
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
    
    Returns:
        Dict with draft details for review.
    """
    try:
        outlook = _get_outlook()
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        if cc:
            mail.CC = cc
        if bcc:
            mail.BCC = bcc

        # Save as draft (don't send yet)
        mail.Save()

        return {
            "success": True,
            "action": "draft_email",
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc,
            "bcc": bcc,
            "details": f"Email draft created in Outlook.\nTo: {to}\nSubject: {subject}",
        }
    except Exception as e:
        logger.warning(f"Outlook COM failed, falling back to mailto: {e}")
        return _mailto_fallback(to, subject, body, cc, bcc)


def _send_email_smtp(to: str, subject: str, body: str, cc: str = "", bcc: str = "",
                     smtp_server_override: Optional[str] = None,
                     smtp_port_override: Optional[int] = None,
                     smtp_email_override: Optional[str] = None,
                     smtp_password_override: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Try to send email via SMTP if configured in .env."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from ..config import settings

    smtp_server = smtp_server_override or settings.smtp_server
    smtp_port = smtp_port_override or settings.smtp_port
    smtp_email = smtp_email_override or settings.smtp_email
    smtp_password = smtp_password_override or settings.smtp_password

    if not all([smtp_server, smtp_email, smtp_password]):
        logger.info("SMTP server credentials not fully configured. Skipping SMTP fallback.")
        return None

    try:
        logger.info(f"Attempting to send email to {to} via SMTP server {smtp_server}...")
        
        # Build message
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = to
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc

        msg.attach(MIMEText(body, 'plain'))

        # Connect & send
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_email, smtp_password)

        recipients = [r.strip() for r in to.split(";") if r.strip()]
        if cc:
            recipients.extend([r.strip() for r in cc.split(";") if r.strip()])
        if bcc:
            recipients.extend([r.strip() for r in bcc.split(";") if r.strip()])

        server.sendmail(smtp_email, recipients, msg.as_string())
        server.quit()

        logger.info("Email sent successfully via SMTP.")
        return {
            "success": True,
            "action": "send_email_smtp",
            "to": to,
            "subject": subject,
            "details": f"Email sent successfully to {to} via SMTP in the background."
        }
    except Exception as smtp_err:
        logger.error(f"SMTP sending failed: {smtp_err}")
        return {
            "success": False,
            "error": f"SMTP connection failed: {str(smtp_err)}"
        }


def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "",
               smtp_server: Optional[str] = None, smtp_port: Optional[int] = None,
               smtp_email: Optional[str] = None, smtp_password: Optional[str] = None) -> Dict[str, Any]:
    """
    Send an email via Outlook immediately.
    
    Should only be called AFTER user approval via ReviewDialog.
    
    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body text.
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
    
    Returns:
        Dict with send status.
    """
    try:
        outlook = _get_outlook()
        mail = outlook.CreateItem(0)
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        if cc:
            mail.CC = cc
        if bcc:
            mail.BCC = bcc

        mail.Send()

        return {
            "success": True,
            "action": "send_email",
            "to": to,
            "subject": subject,
            "details": f"Email sent successfully to {to}.",
        }
    except Exception as e:
        logger.warning(f"Outlook COM failed, trying SMTP: {e}")
        smtp_res = _send_email_smtp(
            to, subject, body, cc, bcc,
            smtp_server_override=smtp_server,
            smtp_port_override=smtp_port,
            smtp_email_override=smtp_email,
            smtp_password_override=smtp_password
        )
        if smtp_res is not None:
            if smtp_res["success"]:
                return smtp_res
            else:
                logger.warning(f"SMTP sending failed ({smtp_res.get('error')}). Falling back to mailto.")
                return _mailto_fallback(to, subject, body, cc, bcc)
        return _mailto_fallback(to, subject, body, cc, bcc)


def read_inbox(count: int = 5, folder: str = "Inbox") -> List[Dict[str, Any]]:
    """
    Read recent emails from the Outlook inbox.
    
    Args:
        count: Number of recent emails to fetch.
        folder: Outlook folder name (default: "Inbox").
    
    Returns:
        List of email summaries.
    """
    try:
        outlook = _get_outlook()
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)  # 6 = olFolderInbox

        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)  # Most recent first

        emails = []
        for i, msg in enumerate(messages):
            if i >= count:
                break
            try:
                emails.append({
                    "index": i + 1,
                    "subject": msg.Subject or "(No Subject)",
                    "sender": msg.SenderName or "Unknown",
                    "sender_email": msg.SenderEmailAddress or "",
                    "received": str(msg.ReceivedTime),
                    "preview": (msg.Body or "")[:200].strip(),
                    "unread": msg.UnRead,
                })
            except Exception:
                continue

        return emails

    except Exception as e:
        logger.error(f"Failed to read inbox: {e}")
        return []


def reply_to_email(index: int, reply_body: str, reply_all: bool = False) -> Dict[str, Any]:
    """
    Reply to an email by its inbox index.
    
    Args:
        index: 1-based index of the email in the inbox (from read_inbox).
        reply_body: The reply message text.
        reply_all: If True, reply to all recipients.
    
    Returns:
        Dict with reply status.
    """
    try:
        outlook = _get_outlook()
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)

        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)

        target_msg = None
        for i, msg in enumerate(messages):
            if i + 1 == index:
                target_msg = msg
                break

        if not target_msg:
            return {"success": False, "error": f"Email at index {index} not found."}

        if reply_all:
            reply = target_msg.ReplyAll()
        else:
            reply = target_msg.Reply()

        reply.Body = reply_body + "\n\n" + reply.Body
        reply.Save()

        return {
            "success": True,
            "action": "reply_email",
            "to": target_msg.SenderEmailAddress,
            "subject": f"RE: {target_msg.Subject}",
            "details": f"Reply draft created for: {target_msg.Subject}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to create reply: {str(e)}"}
