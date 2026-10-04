# Mailing claim links (2026-10-04)

One-off rollout: give every existing person an account by mailing their claim link.

- `manage.py send_claim_links [--dry-run]`, logic in `olympic_warriors/claim_mailing.py` (the command is a thin wrapper).
- Recipients: users with an active player in an active edition (`person_players()`), active, not staff or superuser, not yet claimed (`UserProfile.claimed_at`), with a valid email that is not `@olympicwarriors.com` (subdomains included, case-insensitive). Blank, invalid, internal, claimed, staff and deactivated users are skipped and counted by reason.
- Each user gets their own mail with `claims.claim_link(user)`, their username, the link's validity and a pointer to `/forgot` for an expired link. Users sharing an address are each mailed; the command warns, since self-reset matches nobody for a shared address.
- `--dry-run` lists recipients and skip counts, sends nothing. The command fails early without an absolute `PUBLIC_URL` or with `settings.MAIL_CAN_SEND` false. A failed send is logged by user id, counted, and does not stop the batch.
- Re-running is safe: whoever has claimed drops out; the others get a fresh link (older ones stay valid until they expire). No sent-state is stored.
