import re
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from olympic_warriors import claim_mailing
from olympic_warriors.claims import check_claim
from olympic_warriors.models import UserProfile
from olympic_warriors.tests.test_claims import ClaimSetup


@override_settings(PUBLIC_URL="https://ow.example", MAIL_CAN_SEND=True)
class TestClaimMailing(ClaimSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.lea.password = ""  # unusable, like an imported user
        self.mail(self.lea, "lea@mail.example")

    def mail_to(self, user, email):
        user.email = email
        user.save(update_fields=["email"])

    mail = mail_to

    def run_command(self, *args):
        out = StringIO()
        call_command("send_claim_links", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_sends_a_working_claim_link_to_an_eligible_person(self):
        self.run_command()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["lea@mail.example"])
        self.assertIn("Léa", message.body)
        self.assertIn("leamartin", message.body)
        self.assertIn("/forgot", message.body)
        uid, token = re.search(r"https://ow\.example/claim/([\w-]+)/([\w-]+)", message.body).groups()
        self.assertEqual(check_claim(uid, token), self.lea)

    def test_skips_everyone_else_and_says_why(self):
        self.mail_to(self.staff, "ana@mail.example")
        self.mail_to(self.gone, "gone@mail.example")
        blank = self.person("blank", "Bob", "Blank", self.y2026)
        self.mail_to(blank, "")
        self.mail_to(self.boss, "boss@mail.example")
        self.mail_to(self.benched, "bea@mail.example")  # not a person: no active player
        plan = claim_mailing.plan()
        self.assertEqual(plan.recipients, [self.lea])
        self.assertEqual(
            {reason: [u.username for u in users] for reason, users in plan.skipped.items()},
            {
                "staff": ["ana", "boss"],
                "inactive": ["gone"],
                "no_email": ["blank"],
            },
        )

    def test_blank_internal_invalid_and_claimed_addresses(self):
        blank = self.person("blank", "Bob", "Blank", self.y2026)
        self.mail_to(blank, "  ")
        extra = self.person("deux", "Dee", "Two", self.y2026)
        sub = self.person("trois", "Tri", "Three", self.y2026)
        bad = self.person("quatre", "Quat", "Four", self.y2026)
        done = self.person("cinq", "Cin", "Five", self.y2026)
        self.mail_to(extra, "dee@OLYMPICWARRIORS.com")
        self.mail_to(sub, "tri@mail.olympicwarriors.com")
        self.mail_to(bad, "not-an-address")
        self.mail_to(done, "cin@mail.example")
        UserProfile.objects.create(user=done, claimed_at=timezone.now())
        notours = self.person("six", "Six", "Six", self.y2026)
        self.mail_to(notours, "six@olympicwarriors.com.example")
        plan = claim_mailing.plan()
        self.assertEqual({u.username for u in plan.recipients}, {"leamartin", "six"})
        self.assertEqual([u.username for u in plan.skipped["no_email"]], ["blank"])
        self.assertEqual({u.username for u in plan.skipped["internal"]}, {"deux", "trois"})
        self.assertEqual([u.username for u in plan.skipped["invalid_email"]], ["quatre"])
        self.assertEqual([u.username for u in plan.skipped["claimed"]], ["cinq"])

    def test_shared_address_gets_one_mail_per_user_and_a_warning(self):
        twin = self.person("twin", "Tim", "Martin", self.y2026)
        self.mail_to(twin, "LEA@mail.example")
        out = self.run_command()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            sorted(re.search(r"Identifiant : (\w+)", m.body).group(1) for m in mail.outbox),
            ["leamartin", "twin"],
        )
        self.assertIn("lea@mail.example", out.lower())
        self.assertIn("twin", out)

    def test_dry_run_sends_nothing(self):
        out = self.run_command("--dry-run")
        self.assertEqual(mail.outbox, [])
        self.assertIn("leamartin", out)
        self.assertIn("lea@mail.example", out)

    def test_refuses_without_public_url_or_mail(self):
        with override_settings(PUBLIC_URL=""), self.assertRaises(CommandError):
            self.run_command()
        with override_settings(MAIL_CAN_SEND=False), self.assertRaises(CommandError):
            self.run_command()
        self.assertEqual(mail.outbox, [])

    def test_one_failure_does_not_stop_the_others(self):
        other = self.person("deux", "Dee", "Two", self.y2026)
        self.mail_to(other, "dee@mail.example")
        real = claim_mailing.EmailMessage.send
        calls = []

        def flaky(message, *args, **kwargs):
            calls.append(message.to)
            if message.to == ["lea@mail.example"]:
                raise OSError("smtp down")
            return real(message, *args, **kwargs)

        with mock.patch.object(claim_mailing.EmailMessage, "send", flaky):
            out = self.run_command()
        self.assertEqual(len(calls), 2)
        self.assertEqual([m.to for m in mail.outbox], [["dee@mail.example"]])
        self.assertIn("1 envoyé", out)
        self.assertIn("1 échec", out)
