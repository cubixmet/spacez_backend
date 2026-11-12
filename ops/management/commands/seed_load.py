"""Create additional realistic rows so N+1 / list endpoints stay visible under load."""

from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AccountStatus, MemberProfile, User, UserRole
from attendance.models import AttendanceRecord, AttendanceSource, AttendanceStatus
from billing.models import Invoice, InvoiceKind, InvoiceLineItem, InvoiceStatus, Payment, PaymentMethod, PaymentStatus
from catalog.models import PricingItem
from ops.services import next_invoice_number
from spacez_backend.periods import period_from_start
from subscriptions.models import BillingStatus, Subscription, SubscriptionItem, SubscriptionStatus


class Command(BaseCommand):
    help = "Add ~60 extra members with subscriptions, invoices, payments, and attendance."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=60)

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        space_items = list(PricingItem.objects.filter(code="space", active=True))
        if not space_items:
            self.stderr.write("No active space pricing. Run seed_dev first.")
            return
        created = 0
        today = date.today()
        for i in range(count):
            email = f"load{i:03d}@spacez.in"
            if User.objects.filter(email=email).exists():
                continue
            space = space_items[i % len(space_items)]
            user = User.objects.create_user(
                email=email,
                password="spacez123",
                full_name=f"Load Member {i:03d}",
                phone=f"+91 98{i:08d}",
                role=UserRole.MEMBER,
            )
            member = MemberProfile.objects.create(
                user=user,
                space_type=space.space_type,
                account_status=AccountStatus.ACTIVE,
                proof_type="Aadhaar Card",
                proof_number=f"LOAD-{i:04d}",
                onboarding_completed=True,
                created_at=today - timedelta(days=(i % 40)),
            )
            start = today - timedelta(days=(i % 28))
            period = period_from_start(start, anchor_day=start.day)
            sub = Subscription.objects.create(
                member=member,
                space_type=space.space_type,
                amount=space.price,
                start_date=start,
                period_start=period.start,
                period_end=period.end,
                billing_status=BillingStatus.DUE if i % 3 else BillingStatus.PAID,
                status=SubscriptionStatus.ACTIVE,
            )
            SubscriptionItem.objects.create(
                subscription=sub,
                pricing_item=space,
                code=space.code,
                name=space.name,
                unit_price=space.price,
                quantity=1,
                amount=space.price,
            )
            invoice = Invoice.objects.create(
                number=next_invoice_number(),
                member=member,
                subscription=sub,
                period_start=period.start,
                period_end=period.end,
                total=space.price,
                status=InvoiceStatus.PAID if sub.billing_status == BillingStatus.PAID else InvoiceStatus.DUE,
                issue_date=period.start,
                kind=InvoiceKind.SUBSCRIPTION,
            )
            InvoiceLineItem.objects.create(
                invoice=invoice,
                code=space.code,
                name=space.name,
                unit_price=space.price,
                quantity=1,
                amount=space.price,
                pricing_item_id=str(space.id),
            )
            if sub.billing_status == BillingStatus.PAID:
                Payment.objects.create(
                    member=member,
                    subscription=sub,
                    invoice=invoice,
                    amount=space.price,
                    paid_on=period.start,
                    method=PaymentMethod.UPI,
                    reference=f"LOAD-{i}",
                    status=PaymentStatus.PAID,
                )
            AttendanceRecord.objects.create(
                member=member,
                date=today - timedelta(days=1),
                clock_in=__import__("datetime").time(9, 30),
                clock_out=__import__("datetime").time(18, 0),
                status=AttendanceStatus.PRESENT,
                source=AttendanceSource.ADMIN,
                marked_by="Load seed",
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} load members."))
