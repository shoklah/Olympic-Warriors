"""
DRF permissions for the organiser endpoints.
"""

from rest_framework.permissions import BasePermission


class IsOrganiser(BasePermission):
    """
    Staff users only: anyone who can log into the Django admin can score from the site.
    Anonymous requests get 401 (token auth advertises a challenge), other users 403.
    """

    message = "Organisers only"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
