from datetime import date, time, timedelta
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AccountStatus, MagicLink, MemberProfile, User, UserRole
from accounts.services import create_member
from attendance.models import AttendanceEdit, AttendanceRecord, AttendanceSource, AttendanceStatus
from billing.models import Invoice, InvoiceKind, InvoiceLineItem, InvoiceStatus, Payment, PaymentStatus
from catalog.models import PricingItem
from ops.models import AuditLog, EmailLog, Notification, SiteSettings
from ops.services import next_invoice_number
from spacez_backend.periods import add_days, current_period_for, next_period, period_from_start
from subscriptions.models import BillingStatus, Subscription, SubscriptionAction, SubscriptionEvent, SubscriptionStatus

PROOF_TYPES = ["Aadhaar Card", "PAN Card", "Passport", "Driving Licence", "College ID"]

SEED_MEMBERS = [
    {
        "fullName": "John Mathew",
        "phone": "+91 89215 92742",
        "email": "john@spacez.in",
        "spaceType": "Co-working",
        "status": AccountStatus.ACTIVE,
        "startDay": 10,
        "monthsAgo": 4,
        "codes": ["space", "ac", "laptop"],
        "billing": BillingStatus.DUE,
    },
    {
        "fullName": "Aarav Nair",
        "phone": "+91 90000 12345",
        "email": "new@spacez.in",
        "spaceType": "Student",
        "status": AccountStatus.ACTIVE,
        "startDay": 5,
        "monthsAgo": 2,
        "codes": ["space", "ac"],
        "billing": BillingStatus.PAID,
    },
    {
        "fullName": "Meera Krishnan",
        "phone": "+91 90876 22110",
        "email": "meera@spacez.in",
        "spaceType": "Co-working",
        "status": AccountStatus.ACTIVE,
        "startDay": 18,
        "monthsAgo": 7,
        "codes": ["space", "ac"],
        "billing": BillingStatus.PARTIALLY_PAID,
    },
    {
        "fullName": "Rahul Dev",
        "phone": "+91 99887 44556",
        "email": "rahul@spacez.in",
        "spaceType": "Co-working",
        "status": AccountStatus.SUSPENDED,
        "startDay": 22,
        "monthsAgo": 6,
        "codes": ["space"],
        "billing": BillingStatus.DUE,
    },
    {
        "fullName": "Sneha Pillai",
        "phone": "+91 90123 88990",
        "email": "sneha@spacez.in",
        "spaceType": "Student",
        "status": AccountStatus.ACTIVE,
        "startDay": 1,
        "monthsAgo": 3,
        "codes": ["space", "laptop"],
        "billing": BillingStatus.PAID,
    },
    {
        "fullName": "Vikram Menon",
        "phone": "+91 97654 33221",
        "email": "vikram@spacez.in",
        "spaceType": "Co-working",
        "status": AccountStatus.INACTIVE,
        "startDay": 12,
        "monthsAgo": 9,
        "codes": ["space", "laptop"],
        "billing": BillingStatus.PAID,
    },
    {
        "fullName": "Fathima Rasheed",
        "phone": "+91 91234 55678",
        "email": "fathima@spacez.in",
        "spaceType": "Student",
        "status": AccountStatus.ACTIVE,
        "startDay": 26,
        "monthsAgo": 1,
        "codes": ["space"],
        "billing": BillingStatus.DUE,
    },
    {
        "fullName": "Arjun Suresh",
        "phone": "+91 98111 22334",
        "email": "arjun@spacez.in",
        "spaceType": "Co-working",
        "status": AccountStatus.ACTIVE,
        "startDay": 3,
        "monthsAgo": 5,
        "codes": ["space", "ac", "laptop", "locker"],
        "billing": BillingStatus.PAID,
    },
]


def _start_date(spec) -> date:
    today = date.today()
    month = today.month - spec["monthsAgo"]
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(spec["startDay"], 28)
    return date(year, month, day)


def _pricing_map():
    items = {}
    for item in PricingItem.objects.all():
        items[(item.space_type, item.code, item.version)] = item
        if item.active:
            items[(item.space_type, item.code, "active")] = item
    return items


def _line(item: PricingItem):
    return SimpleNamespace(
        code=item.code,
        name=item.name,
        unit_price=item.price,
        quantity=1,
        amount=item.price,
        pricing_item_id=str(item.id),
    )


class Command(BaseCommand):
    help = "Load Space Z development data matching the React mock workspace."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing operational data first.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._wipe()
        elif User.objects.filter(email="admin@spacez.in").exists() and MemberProfile.objects.exists():
            self.stdout.write(self.style.WARNING("Development data already exists. Use --reset to rebuild."))
            return

        year = date.today().year
        settings_obj = SiteSettings.load()
        settings_obj.space_name = "Space Z"
        settings_obj.powered_by = "Powered by Cubixmet"
        settings_obj.address = "Space Z Workspace, Cubixmet Technologies"
        settings_obj.support_email = "hello@cubixmet.com"
        settings_obj.support_phone = "+91 98470 11223"
        settings_obj.currency = "INR (₹)"
        settings_obj.invoice_prefix = f"SZ-{year}-"
        settings_obj.billing_rule = "Anniversary based (calendar month)"
        settings_obj.grace_period_days = 5
        settings_obj.allow_admin_attendance_edit = True
        settings_obj.allow_member_clock_out_edit = False
        settings_obj.default_attendance_status = AttendanceStatus.PRESENT
        settings_obj.notify_new_member = True
        settings_obj.notify_payment = True
        settings_obj.notify_billing_due = True
        settings_obj.notify_attendance = False
        settings_obj.invoice_sequence = 100
        settings_obj.save()

        admin = self._admin()
        pricing = self._pricing(year)
        members = []
        for index, spec in enumerate(SEED_MEMBERS):
            members.append(self._member(spec, index, admin, pricing))

        self._attendance(members, admin)
        self._notifications()
        self.stdout.write(self.style.SUCCESS("Seeded Space Z development data."))
        self.stdout.write("Admin: admin@spacez.in / spacez@admin")
        self.stdout.write("Member (ACTIVE+DUE): john@spacez.in / spacez123")
        self.stdout.write("Member (first-time onboarding): new@spacez.in / spacez123")

    def _wipe(self):
        AttendanceEdit.objects.all().delete()
        AttendanceRecord.objects.all().delete()
        Payment.objects.all().delete()
        InvoiceLineItem.objects.all().delete()
        Invoice.objects.all().delete()
        SubscriptionEvent.objects.all().delete()
        Subscription.objects.all().delete()
        MagicLink.objects.all().delete()
        Notification.objects.all().delete()
        AuditLog.objects.all().delete()
        EmailLog.objects.all().delete()
        MemberProfile.objects.all().delete()
        User.objects.filter(role=UserRole.MEMBER).delete()
        PricingItem.objects.all().delete()
        User.objects.filter(email="admin@spacez.in").delete()

    def _admin(self) -> User:
        admin, created = User.objects.get_or_create(
            email="admin@spacez.in",
            defaults={
                "full_name": "Fadhil M",
                "phone": "+91 98470 11223",
                "role": UserRole.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.full_name = "Fadhil M"
        admin.phone = "+91 98470 11223"
        admin.role = UserRole.SUPER_ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("spacez@admin")
        admin.save()
        return admin

    def _pricing(self, year: int):
        specs = [
            ("space", "Space (Co-working desk)", "Co-working", 1099, date(year - 1, 4, 1), False, 1),
            ("space", "Space (Co-working desk)", "Co-working", 1199, date(year, 1, 1), True, 2),
            ("ac", "Air Conditioning", "Co-working", 300, date(year - 1, 4, 1), True, 1),
            ("laptop", "Laptop Access", "Co-working", 300, date(year - 1, 4, 1), True, 1),
            ("space", "Space (Student seat)", "Student", 1199, date(year - 1, 4, 1), True, 1),
            ("ac", "Air Conditioning", "Student", 300, date(year - 1, 4, 1), True, 1),
            ("laptop", "Laptop Access", "Student", 300, date(year - 1, 4, 1), True, 1),
            ("locker", "Personal Locker", "Co-working", 150, date(year, 1, 1), True, 1),
        ]
        created = []
        for code, name, space_type, price, effective, active, version in specs:
            item, _ = PricingItem.objects.get_or_create(
                code=code,
                space_type=space_type,
                version=version,
                defaults={
                    "name": name,
                    "price": price,
                    "effective_date": effective,
                    "active": active,
                },
            )
            item.name = name
            item.price = price
            item.effective_date = effective
            item.active = active
            item.save()
            created.append(item)
        return created

    def _member(self, spec, index, admin, pricing):
        start = _start_date(spec)
        price_map = _pricing_map()
        item_ids = [str(price_map[(spec["spaceType"], code, "active")].id) for code in spec["codes"]]
        existing = User.objects.filter(email=spec["email"]).first()
        if existing:
            return existing.member_profile
        result = create_member(
            data={
                "fullName": spec["fullName"],
                "phone": spec["phone"],
                "email": spec["email"],
                "proofType": PROOF_TYPES[index % len(PROOF_TYPES)],
                "proofNumber": f"XXXX-{4321 + index}",
                "notes": "",
            },
            subscription_data={
                "startDate": start,
                "spaceType": spec["spaceType"],
                "pricingItemIds": item_ids,
            },
            payment_data=None,
            admin=admin,
        )
        member = result["member"]
        subscription = result["subscription"]
        current_invoice = result["invoice"]
        member.account_status = spec["status"]
        member.onboarding_completed = spec["email"] != "new@spacez.in"
        member.save(update_fields=["account_status", "onboarding_completed"])

        old_space = price_map.get(("Co-working", "space", 1))
        current_items = list(subscription.items.all())
        cursor = period_from_start(start)
        current = current_period_for(start)
        hist = 0
        while cursor.end < current.start and hist < 24:
            snap = []
            for item in current_items:
                if spec["email"] == "john@spacez.in" and hist == 0 and item.code == "space" and old_space:
                    snap.append(_line(old_space))
                else:
                    snap.append(
                        SimpleNamespace(
                            code=item.code,
                            name=item.name,
                            unit_price=item.unit_price,
                            quantity=item.quantity,
                            amount=item.amount,
                            pricing_item_id=str(item.pricing_item_id or ""),
                        )
                    )
            total = sum(row.amount for row in snap)
            invoice = Invoice.objects.create(
                number=next_invoice_number(),
                member=member,
                subscription=subscription,
                period_start=cursor.start,
                period_end=cursor.end,
                total=total,
                status=InvoiceStatus.PAID,
                issue_date=cursor.start,
                kind=InvoiceKind.SUBSCRIPTION,
            )
            for row in snap:
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    code=row.code,
                    name=row.name,
                    unit_price=row.unit_price,
                    quantity=row.quantity,
                    amount=row.amount,
                    pricing_item_id=row.pricing_item_id,
                )
            Payment.objects.create(
                member=member,
                subscription=subscription,
                invoice=invoice,
                amount=total,
                paid_on=add_days(cursor.start, 1),
                method="UPI" if hist % 2 == 0 else "Bank Transfer",
                reference=f"REF{73210 + hist + index * 10}",
                notes="",
                status=PaymentStatus.PAID,
            )
            cursor = next_period(cursor.end)
            hist += 1

        current_invoice.issue_date = current.start
        current_invoice.period_start = current.start
        current_invoice.period_end = current.end
        current_invoice.save(update_fields=["issue_date", "period_start", "period_end"])

        if spec["billing"] != BillingStatus.DUE:
            amount = subscription.amount if spec["billing"] == BillingStatus.PAID else round(subscription.amount / 2)
            Payment.objects.create(
                member=member,
                subscription=subscription,
                invoice=current_invoice,
                amount=amount,
                paid_on=add_days(current.start, 1),
                method="UPI" if index % 2 == 0 else "Bank Transfer",
                reference=f"REF{74000 + index}",
                notes="Partial collection" if spec["billing"] == BillingStatus.PARTIALLY_PAID else "",
                status=PaymentStatus.PAID,
            )
        current_invoice.status = spec["billing"]
        current_invoice.save(update_fields=["status"])
        subscription.billing_status = spec["billing"]
        if spec["status"] == AccountStatus.INACTIVE:
            subscription.status = SubscriptionStatus.CANCELLED
        subscription.save(update_fields=["billing_status", "status"])

        if spec["email"] == "meera@spacez.in":
            SubscriptionEvent.objects.create(
                subscription=subscription,
                member=member,
                action=SubscriptionAction.UPGRADED,
                admin="Fadhil M",
                old_value="Space (Co-working desk) · ₹1,199",
                new_value="Space (Co-working desk), Air Conditioning · ₹1,499",
                adjustment=174,
                note="Added AC mid-cycle",
            )
        return member

    def _attendance(self, members, admin):
        today = date.today()
        active = [m for m in members if m.account_status == AccountStatus.ACTIVE]
        meera_record = None
        for day_offset in range(40):
            on_date = today - timedelta(days=day_offset)
            if on_date.weekday() == 6:
                continue
            for member_index, member in enumerate(active):
                seed = day_offset * 7 + member_index * 3
                if seed % 9 == 0:
                    continue
                in_hour = 9 + (seed % 2)
                in_minute = (seed * 13) % 60
                partial = seed % 11 == 0
                still_inside = day_offset == 0 and member_index % 3 == 0
                out_hour = 13 if partial else 17 + (seed % 3)
                out_minute = (seed * 7) % 60
                record = AttendanceRecord.objects.create(
                    member=member,
                    date=on_date,
                    clock_in=time(in_hour, in_minute),
                    clock_out=None if still_inside else time(out_hour, out_minute),
                    status=AttendanceStatus.PARTIAL if partial else AttendanceStatus.PRESENT,
                    source=AttendanceSource.ADMIN if seed % 8 == 0 else AttendanceSource.MEMBER,
                    marked_by="Fadhil M" if seed % 8 == 0 else member.user.full_name,
                    note="",
                )
                if member.user.email == "meera@spacez.in" and meera_record is None:
                    meera_record = record
        if meera_record:
            AttendanceEdit.objects.create(
                record=meera_record,
                admin="Fadhil M",
                field="clockIn",
                from_value="09:32",
                to_value=meera_record.clock_in.strftime("%H:%M") if meera_record.clock_in else "09:15",
                reason="Forgot to clock in — corrected from front desk",
            )

    def _ensure_notification(self, title, body, kind, read=False, member=None):
        qs = Notification.objects.filter(title=title, member=member)
        if qs.exists():
            return qs.first()
        return Notification.objects.create(title=title, body=body, kind=kind, read=read, member=member)

    def _notifications(self):
        self._ensure_notification(
            "Payment due",
            "John Mathew has an outstanding balance for the current billing period.",
            "billing",
        )
        self._ensure_notification(
            "Payment recorded",
            "₹1,049 received from Sneha Pillai via UPI.",
            "payment",
        )
        self._ensure_notification(
            "Attendance modified",
            "Meera Krishnan's clock-in was corrected by an admin.",
            "attendance",
            read=True,
        )
        john = MemberProfile.objects.filter(user__email="john@spacez.in").first()
        if john:
            self._ensure_notification(
                "Welcome to Space Z",
                "Your membership is active. Clock in from the member app when you arrive.",
                "member",
                member=john,
            )
