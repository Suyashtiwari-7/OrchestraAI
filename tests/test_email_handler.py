"""
OrchestraAI — Email Handler Tests
=================================
Tests for the Outlook COM email automation.
Uses mocking to prevent actual Outlook interactions.
"""

import pytest
from unittest.mock import patch, MagicMock
from orchestra.tools.email_handler import draft_email, send_email, read_inbox, reply_to_email


class TestEmailHandler:
    """Test Outlook automation, drafts, sending, and reading inbox."""

    @patch("win32com.client.Dispatch")
    def test_draft_email(self, mock_dispatch):
        """Test drafting an email."""
        mock_outlook = MagicMock()
        mock_mail = MagicMock()
        mock_outlook.CreateItem.return_value = mock_mail
        mock_dispatch.return_value = mock_outlook

        res = draft_email(to="test@example.com", subject="Hello", body="This is a test body")

        assert res["success"] is True
        assert res["to"] == "test@example.com"
        assert res["subject"] == "Hello"
        mock_outlook.CreateItem.assert_called_once_with(0)
        assert mock_mail.To == "test@example.com"
        assert mock_mail.Subject == "Hello"
        assert mock_mail.Body == "This is a test body"
        mock_mail.Save.assert_called_once()

    @patch("win32com.client.Dispatch")
    def test_send_email(self, mock_dispatch):
        """Test sending an email."""
        mock_outlook = MagicMock()
        mock_mail = MagicMock()
        mock_outlook.CreateItem.return_value = mock_mail
        mock_dispatch.return_value = mock_outlook

        res = send_email(to="test@example.com", subject="Hello", body="This is a test body")

        assert res["success"] is True
        mock_outlook.CreateItem.assert_called_once_with(0)
        assert mock_mail.To == "test@example.com"
        mock_mail.Send.assert_called_once()

    @patch("win32com.client.Dispatch")
    def test_read_inbox(self, mock_dispatch):
        """Test reading the inbox."""
        mock_outlook = MagicMock()
        mock_ns = MagicMock()
        mock_inbox = MagicMock()
        mock_messages = [MagicMock(), MagicMock()]
        
        mock_messages[0].Subject = "Mail 1"
        mock_messages[0].SenderName = "Sender 1"
        mock_messages[0].SenderEmailAddress = "s1@test.com"
        mock_messages[0].ReceivedTime = "2026-06-08 12:00:00"
        mock_messages[0].Body = "Body 1 content here"
        mock_messages[0].UnRead = True

        mock_messages[1].Subject = "Mail 2"
        mock_messages[1].SenderName = "Sender 2"
        mock_messages[1].SenderEmailAddress = "s2@test.com"
        mock_messages[1].ReceivedTime = "2026-06-08 11:00:00"
        mock_messages[1].Body = "Body 2 content here"
        mock_messages[1].UnRead = False

        mock_items = MagicMock()
        mock_items.Sort = MagicMock()
        mock_items.__iter__.return_value = iter(mock_messages)
        mock_items.__getitem__.side_effect = lambda idx: mock_messages[idx]

        mock_inbox.Items = mock_items
        mock_ns.GetDefaultFolder.return_value = mock_inbox
        mock_outlook.GetNamespace.return_value = mock_ns
        mock_dispatch.return_value = mock_outlook

        emails = read_inbox(count=2)

        assert len(emails) == 2
        assert emails[0]["subject"] == "Mail 1"
        assert emails[0]["sender"] == "Sender 1"
        assert emails[1]["subject"] == "Mail 2"
        mock_ns.GetDefaultFolder.assert_called_once_with(6)

    @patch("win32com.client.Dispatch")
    def test_reply_to_email(self, mock_dispatch):
        """Test replying to an email."""
        mock_outlook = MagicMock()
        mock_ns = MagicMock()
        mock_inbox = MagicMock()
        mock_msg = MagicMock()
        mock_reply = MagicMock()

        mock_msg.Subject = "Original Subject"
        mock_msg.SenderEmailAddress = "original@sender.com"
        mock_msg.Reply.return_value = mock_reply
        mock_reply.Body = "Old body content"

        mock_items = MagicMock()
        mock_items.Sort = MagicMock()
        mock_items.__iter__.return_value = iter([mock_msg])
        mock_items.__getitem__.side_effect = lambda idx: [mock_msg][idx]

        mock_inbox.Items = mock_items
        mock_ns.GetDefaultFolder.return_value = mock_inbox
        mock_outlook.GetNamespace.return_value = mock_ns
        mock_dispatch.return_value = mock_outlook

        res = reply_to_email(index=1, reply_body="This is my reply")

        assert res["success"] is True
        assert res["to"] == "original@sender.com"
        mock_msg.Reply.assert_called_once()
        assert "This is my reply" in mock_reply.Body
        mock_reply.Save.assert_called_once()
