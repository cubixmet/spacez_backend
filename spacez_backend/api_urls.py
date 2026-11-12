from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views as accounts_views
from attendance import views as attendance_views
from billing import views as billing_views
from catalog import views as catalog_views
from ops import views as ops_views
from subscriptions import views as subscriptions_views

urlpatterns = [
    # Auth
    path("auth/admin/login/", accounts_views.admin_login),
    path("auth/member/login/", accounts_views.member_login),
    path("auth/member/magic/", accounts_views.member_magic_login),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/password-reset/", accounts_views.password_reset),
    # Public
    path("public/enquiries/", ops_views.public_enquiry),
    path("public/contact/", ops_views.public_contact),
    path("public/plans/", ops_views.public_plans),
    # Admin
    path("admin/me/", accounts_views.admin_me),
    path("admin/dashboard/", ops_views.dashboard),
    path("admin/reports/", ops_views.reports),
    path("admin/settings/", ops_views.settings_view),
    path("admin/notifications/", ops_views.notifications_collection),
    path("admin/notifications/read-all/", ops_views.notifications_read_all),
    path("admin/audit-logs/", ops_views.audit_logs),
    path("admin/email-logs/", ops_views.email_logs),
    path("admin/members/", accounts_views.members_collection),
    path("admin/members/<uuid:member_id>/", accounts_views.member_detail),
    path("admin/members/<uuid:member_id>/status/", accounts_views.member_status),
    path("admin/members/<uuid:member_id>/magic-link/", accounts_views.member_magic_link),
    path("admin/pricing/", catalog_views.pricing_collection),
    path("admin/pricing/<uuid:item_id>/toggle/", catalog_views.pricing_toggle),
    path("admin/pricing/<uuid:item_id>/versions/", catalog_views.pricing_new_version),
    path("admin/subscriptions/", subscriptions_views.subscriptions_collection),
    path("admin/subscriptions/<uuid:subscription_id>/", subscriptions_views.subscription_detail),
    path("admin/subscriptions/<uuid:subscription_id>/preview/", subscriptions_views.subscription_preview),
    path("admin/subscriptions/<uuid:subscription_id>/change/", subscriptions_views.subscription_change),
    path("admin/subscriptions/<uuid:subscription_id>/renew/", subscriptions_views.subscription_renew),
    path("admin/subscriptions/<uuid:subscription_id>/cancel/", subscriptions_views.subscription_cancel),
    path("admin/subscriptions/<uuid:subscription_id>/events/", subscriptions_views.subscription_events),
    path("admin/subscription-events/", subscriptions_views.all_subscription_events),
    path("admin/payments/", billing_views.payments_collection),
    path("admin/invoices/", billing_views.invoices_collection),
    path("admin/invoices/<uuid:invoice_id>/", billing_views.invoice_detail),
    path("admin/invoices/generate/", billing_views.invoice_generate),
    path("admin/attendance/", attendance_views.attendance_collection),
    path("admin/attendance/<uuid:record_id>/", attendance_views.attendance_edit),
    path("admin/attendance/bulk/", attendance_views.attendance_bulk),
    # Member PWA
    path("member/me/", accounts_views.member_me),
    path("member/onboarding/", accounts_views.complete_onboarding),
    path("member/subscription/", subscriptions_views.member_subscription),
    path("member/payments/", billing_views.member_payments),
    path("member/invoices/", billing_views.member_invoices),
    path("member/attendance/", attendance_views.member_attendance),
    path("member/attendance/clock-in/", attendance_views.member_clock_in),
    path("member/attendance/clock-out/", attendance_views.member_clock_out),
    path("member/notifications/", ops_views.member_notifications),
    path("member/notifications/read-all/", ops_views.member_notifications_read),
]
