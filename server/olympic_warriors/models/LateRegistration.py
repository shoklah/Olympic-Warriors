from django.contrib.auth.models import User
from django.db import models


class LateRegistration(models.Model):
    """
    A per-user exemption from an edition's registration window, for the replacement of a
    forfeiting player (registration_state.py). It is valid until it is deleted or the
    edition's end_date has passed. Not exported with an edition (transfer.NOT_EXPORTED):
    it is an organiser's decision about a person, taken on the database it was taken on.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "edition"], name="late_registration_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.edition.year})"
