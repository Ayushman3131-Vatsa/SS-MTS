"""Compatibility alias for the renamed tenant user account model."""

from app.auth.models.user_account import UserAccount

User = UserAccount

__all__ = ["User"]
