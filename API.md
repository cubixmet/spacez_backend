# Space Z API reference

Base URL (development): `http://127.0.0.1:8000/api`

All authenticated requests use:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

File uploads (`photo`, `proofDocument`) use `multipart/form-data`. JSON bodies and responses use the same camelCase keys as the React mock types.

Errors:

```json
{ "detail": "Human-readable message", "errors": {} }
```

There is no GPS, maps, or payment-gateway integration. Admins record payments manually.

---

## Auth

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/admin/login/` | public | Admin/staff login |
| POST | `/auth/member/login/` | public | Member login |
| POST | `/auth/member/magic/` | public | Consume magic-link token |
| POST | `/auth/refresh/` | public | Refresh JWT (`{ "refresh" }`) |
| POST | `/auth/password-reset/` | public | Queue a reset email (logged, not sent) |

### Admin login body

```json
{ "email": "admin@spacez.in", "password": "spacez@admin", "remember": true }
```

Response: `{ "access", "refresh", "admin": { id, name, email, role, phone } }`

Only `SUPER_ADMIN` and `STAFF` may use the admin login.

### Member login body

```json
{ "email": "john@spacez.in", "password": "spacez123", "remember": true }
```

Response: `{ "access", "refresh", "user": { id, fullName, email, phone, spaceType, accountStatus, photoUrl, onboardingCompleted, memberSince } }`

`user.id` is the **member profile** UUID (the frontend `memberId`).

### Magic link

```json
{ "token": "<token from admin send-magic-link>" }
```

One-time. Used tokens cannot be reused.

---

## Public

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/` | Liveness |
| GET | `/public/plans/` | Active pricing grouped by space type |
| POST | `/public/enquiries/` | Registration / plan request |
| POST | `/public/contact/` | Contact form |

Enquiry body: `{ fullName, phone, email, spaceType, addOns, message, estimatedTotal }`

---

## Admin — session & ops

Requires admin JWT.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/me/` | Current admin user |
| GET | `/admin/dashboard/` | Counts: members, revenue, attendance, billing |
| GET | `/admin/reports/?from=&to=` | Revenue, billed, attendance hours, new members |
| GET/PATCH | `/admin/settings/` | Site settings singleton |
| GET | `/admin/notifications/` | Admin-wide notifications |
| POST | `/admin/notifications/read-all/` | Mark admin notifications read |
| GET | `/admin/audit-logs/` | Audit trail |
| GET | `/admin/email-logs/` | Magic-link / invoice / general email log |

---

## Admin — members

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/members/` | List (`q`, `spaceType`, `accountStatus`) |
| POST | `/admin/members/` | Create member + subscription + optional payment |
| GET | `/admin/members/{id}/` | Detail, latest magic link, subscription id |
| PATCH | `/admin/members/{id}/` | Edit profile / notes / photo |
| POST | `/admin/members/{id}/status/` | `{ status, reason }` ACTIVE / INACTIVE / SUSPENDED |
| POST | `/admin/members/{id}/magic-link/` | Issue one-time onboarding link |

Create body:

```json
{
  "member": {
    "fullName": "Jane Doe",
    "phone": "+91 90000 00000",
    "email": "jane@spacez.in",
    "spaceType": "Co-working",
    "proofType": "Aadhaar Card",
    "proofNumber": "XXXX-1234",
    "notes": ""
  },
  "subscription": {
    "startDate": "2026-08-10",
    "spaceType": "Co-working",
    "pricingItemIds": ["<uuid>", "<uuid>"]
  },
  "payment": {
    "amount": 1799,
    "method": "UPI",
    "reference": "UPI123",
    "paidOn": "2026-08-10"
  }
}
```

`payment` may be omitted. Account status is independent of billing status: **ACTIVE + DUE members can still clock in**.

---

## Admin — catalog

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/pricing/` | All versions (`spaceType`, `active=true`) |
| POST | `/admin/pricing/` | Add item `{ name, code, spaceType, price, effectiveDate, active }` |
| POST | `/admin/pricing/{id}/toggle/` | Activate / deactivate |
| POST | `/admin/pricing/{id}/versions/` | `{ price, effectiveDate }` — deactivates previous version |

Historical invoices never re-read live prices.

---

## Admin — subscriptions

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/subscriptions/` | List |
| POST | `/admin/subscriptions/` | `{ memberId, startDate, spaceType, pricingItemIds }` |
| GET | `/admin/subscriptions/{id}/` | Detail + events |
| GET | `/admin/subscriptions/{id}/events/` | History |
| POST | `/admin/subscriptions/{id}/preview/` | Proration preview |
| POST | `/admin/subscriptions/{id}/change/` | Mid-cycle upgrade/downgrade |
| POST | `/admin/subscriptions/{id}/renew/` | Next anniversary period |
| POST | `/admin/subscriptions/{id}/cancel/` | Mark cancelled |

Change / preview body: `{ pricingItemIds, changeDate?, note? }`

Billing periods are **anniversary-based** (start 10 May → end 9 June). Never start + 30 days. Mid-cycle changes prorate remaining inclusive days.

---

## Admin — billing

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/payments/?memberId=&method=&status=&from=&to=` | List |
| POST | `/admin/payments/` | Record a manual payment |
| GET | `/admin/invoices/?memberId=` | List (line items are frozen snapshots) |
| GET | `/admin/invoices/{id}/` | Detail |
| POST | `/admin/invoices/generate/` | `{ subscriptionId }` |

Payment body: `{ memberId, subscriptionId?, invoiceId?, amount, method, reference, notes, paidOn }`

Methods: `Cash`, `UPI`, `Bank Transfer`, `Card`, `Other`.

Invoice `kind`: `SUBSCRIPTION` | `ADJUSTMENT` | `CREDIT`. Status: `PAID` | `DUE` | `PARTIALLY_PAID` | `CREDIT`.

---

## Admin — attendance

No location fields.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/attendance/?date=&memberId=&status=&source=&q=` | List |
| POST | `/admin/attendance/` | Mark one member |
| PATCH | `/admin/attendance/{id}/` | Audited edit `{ clockIn, clockOut, status, reason }` |
| POST | `/admin/attendance/bulk/` | `{ date, entries: [{ memberId, status }] }` |

Times are `HH:mm`. Source is `MEMBER` or `ADMIN`. Edits are stored on the record.

---

## Member PWA

Requires member JWT.

| Method | Path | Purpose |
| --- | --- | --- |
| GET/PATCH | `/member/me/` | Profile; PATCH `{ phone, photo, password }` |
| POST | `/member/onboarding/` | `{ password, photo? }` first-time complete |
| GET | `/member/subscription/` | Current plan + billing status |
| GET | `/member/payments/` | Payment history |
| GET | `/member/invoices/` | Invoices with snapshot line items |
| GET | `/member/attendance/?from=&to=` | Attendance history |
| POST | `/member/attendance/clock-in/` | Today, ACTIVE accounts only (DUE billing allowed) |
| POST | `/member/attendance/clock-out/` | Today |
| GET | `/member/notifications/` | Stored + generated billing/renewal notices |
| POST | `/member/notifications/read-all/` | Mark stored notifications read |

---

## Mapping from frontend mock services

| `adminApi.ts` / `memberApi.ts` | Endpoint |
| --- | --- |
| `adminLogin` | `POST /auth/admin/login/` |
| `login` | `POST /auth/member/login/` |
| `consumeMagicLink` | `POST /auth/member/magic/` |
| `requestPasswordReset` | `POST /auth/password-reset/` |
| `createMember` | `POST /admin/members/` |
| `updateMember` | `PATCH /admin/members/{id}/` |
| `changeMemberStatus` | `POST /admin/members/{id}/status/` |
| `sendMagicLink` | `POST /admin/members/{id}/magic-link/` |
| `addPricingItem` | `POST /admin/pricing/` |
| `togglePricingItem` | `POST /admin/pricing/{id}/toggle/` |
| `createPriceVersion` | `POST /admin/pricing/{id}/versions/` |
| `createSubscription` | `POST /admin/subscriptions/` |
| `previewChange` | `POST /admin/subscriptions/{id}/preview/` |
| `changeSubscriptionItems` | `POST /admin/subscriptions/{id}/change/` |
| `renewSubscription` | `POST /admin/subscriptions/{id}/renew/` |
| `cancelSubscription` | `POST /admin/subscriptions/{id}/cancel/` |
| `recordPayment` | `POST /admin/payments/` |
| `generateInvoice` | `POST /admin/invoices/generate/` |
| `markAttendance` | `POST /admin/attendance/` |
| `editAttendance` | `PATCH /admin/attendance/{id}/` |
| `bulkMarkAttendance` | `POST /admin/attendance/bulk/` |
| `getReports` | `GET /admin/reports/` |
| `updateSettings` | `PATCH /admin/settings/` |
| `clockIn` / `clockOut` | `POST /member/attendance/clock-in/` / `clock-out/` |
| `completeOnboarding` | `POST /member/onboarding/` |
| `updateProfile` | `PATCH /member/me/` |
