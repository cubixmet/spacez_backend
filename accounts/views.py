import json
import secrets

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView

from django.db.models import Prefetch, Q

from accounts.models import AccountStatus, MagicLink, MemberProfile, User, UserRole
from accounts.permissions import IsAdminRole, IsMemberRole
from accounts.serializers import (
    AdminProfileSerializer,
    LoginSerializer,
    MagicLinkSerializer,
    MemberUpdateSerializer,
    MemberWriteSerializer,
    OnboardingSerializer,
    PasswordResetSerializer,
    ProfileUpdateSerializer,
    StatusSerializer,
    admin_user_payload,
    member_admin_payload,
    member_user_payload,
)
from accounts.services import (
    assert_member_can_sign_in,
    authenticate,
    change_member_status,
    consume_magic_link,
    create_magic_link,
    create_member,
    issue_tokens,
)
from ops.models import EmailKind
from ops.services import log_audit, log_email, magic_link_url
from subscriptions.models import Subscription


def _member_profile(user: User) -> MemberProfile:
    return user.member_profile


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        serializer.validated_data["email"],
        serializer.validated_data["password"],
        expected_roles={UserRole.SUPER_ADMIN, UserRole.STAFF},
    )
    log_audit("Admin signed in", user.email, "Admin session started", admin=user.full_name)
    return Response({**issue_tokens(user), "admin": admin_user_payload(user)})


@api_view(["POST"])
@permission_classes([AllowAny])
def member_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        serializer.validated_data["email"],
        serializer.validated_data["password"],
        expected_roles={UserRole.MEMBER},
    )
    profile = assert_member_can_sign_in(user)
    return Response({**issue_tokens(user), "user": member_user_payload(profile, request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def member_magic_login(request):
    serializer = MagicLinkSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = consume_magic_link(serializer.validated_data["token"])
    profile = assert_member_can_sign_in(user)
    return Response({**issue_tokens(user), "user": member_user_payload(profile, request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset(request):
    serializer = PasswordResetSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].strip()
    # Always return the same message so callers cannot probe which emails exist.
    detail = "If that email is registered, a sign-in link has been sent. Open it, then set a new password in Profile."
    member = (
        MemberProfile.objects.select_related("user")
        .filter(user__email__iexact=email, user__role=UserRole.MEMBER, account_status=AccountStatus.ACTIVE)
        .first()
    )
    if member:
        token = secrets.token_urlsafe(24)
        MagicLink.objects.create(member=member, token=token)
        url = magic_link_url(token)
        log_email(
            to=member.user.email,
            subject="Reset your Space Z password",
            body=(
                f"Hi {member.user.full_name},\n\n"
                f"Use this one-time link to sign in, then set a new password in Profile:\n{url}\n\n"
                "If you did not request this, you can ignore this email."
            ),
            kind=EmailKind.MAGIC_LINK,
        )
    return Response({"detail": detail})


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


@api_view(["GET", "PATCH"])
@permission_classes([IsAdminRole])
def admin_me(request):
    if request.method == "GET":
        return Response(admin_user_payload(request.user))
    serializer = AdminProfileSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    updates = []
    if "name" in data:
        request.user.full_name = data["name"]
        updates.append("full_name")
    if "phone" in data:
        request.user.phone = data["phone"]
        updates.append("phone")
    if updates:
        request.user.save(update_fields=updates)
        log_audit("Admin profile updated", request.user.email, ", ".join(updates), admin=request.user.full_name)
    return Response(admin_user_payload(request.user))


@api_view(["GET", "PATCH"])
@permission_classes([IsMemberRole])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def member_me(request):
    profile = _member_profile(request.user)
    if request.method == "GET":
        return Response(member_user_payload(profile, request))
    serializer = ProfileUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if "phone" in data:
        request.user.phone = data["phone"]
        request.user.save(update_fields=["phone"])
    if "photo" in data:
        profile.photo = data["photo"]
        profile.save(update_fields=["photo"])
    if data.get("password"):
        request.user.set_password(data["password"])
        request.user.save()
    return Response(member_user_payload(profile, request))


@api_view(["POST"])
@permission_classes([IsMemberRole])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def complete_onboarding(request):
    profile = _member_profile(request.user)
    serializer = OnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data["password"])
    request.user.save()
    if serializer.validated_data.get("photo"):
        profile.photo = serializer.validated_data["photo"]
    profile.onboarding_completed = True
    profile.save()
    return Response(member_user_payload(profile, request))


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def members_collection(request):
    if request.method == "GET":
        qs = MemberProfile.objects.select_related("user").prefetch_related(
            Prefetch("magic_links", queryset=MagicLink.objects.order_by("-created_at"))
        )
        q = request.query_params.get("q")
        space = request.query_params.get("spaceType")
        status_filter = request.query_params.get("accountStatus")
        if q:
            qs = qs.filter(Q(user__full_name__icontains=q) | Q(user__email__icontains=q) | Q(user__phone__icontains=q))
        if space:
            qs = qs.filter(space_type=space)
        if status_filter:
            qs = qs.filter(account_status=status_filter)
        return Response([member_admin_payload(m, request) for m in qs.distinct()])

    payload = request.data
    raw_member = payload.get("member")
    if isinstance(raw_member, str):
        member_data = json.loads(raw_member)
    elif isinstance(raw_member, dict):
        member_data = raw_member
    else:
        member_data = {
            key: payload.get(key)
            for key in ("fullName", "phone", "email", "spaceType", "proofType", "proofNumber", "notes")
            if key in payload
        }
    subscription = payload.get("subscription")
    if isinstance(subscription, str):
        subscription = json.loads(subscription)
    if not isinstance(subscription, dict):
        subscription = {}
    if not subscription.get("startDate"):
        subscription["startDate"] = payload.get("startDate")
    if not subscription.get("spaceType"):
        subscription["spaceType"] = payload.get("spaceType") or member_data.get("spaceType")
    ids = subscription.get("pricingItemIds") or payload.get("pricingItemIds") or []
    if isinstance(ids, str):
        ids = json.loads(ids)
    if not isinstance(ids, list):
        ids = list(ids) if ids else []
    subscription["pricingItemIds"] = ids
    payment = payload.get("payment")
    if isinstance(payment, str):
        payment = json.loads(payment)
    write = MemberWriteSerializer(data=member_data)
    write.is_valid(raise_exception=True)
    if not ids:
        return Response({"detail": "Select at least one pricing item."}, status=400)
    result = create_member(
        data={**write.validated_data, "photo": request.FILES.get("photo"), "proofDocument": request.FILES.get("proofDocument")},
        subscription_data={
            "startDate": subscription["startDate"],
            "spaceType": subscription.get("spaceType") or write.validated_data.get("spaceType"),
            "pricingItemIds": ids,
        },
        payment_data=payment,
        admin=request.user,
    )
    return Response(
        {
            "member": member_admin_payload(result["member"], request),
            "subscriptionId": str(result["subscription"].id),
            "invoiceId": str(result["invoice"].id),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminRole])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def member_detail(request, member_id):
    from django.db.models import Prefetch
    from rest_framework.exceptions import ValidationError
    from subscriptions.models import Subscription

    member = (
        MemberProfile.objects.select_related("user")
        .prefetch_related(
            Prefetch("magic_links", queryset=MagicLink.objects.order_by("-created_at")),
            Prefetch("subscriptions", queryset=Subscription.objects.order_by("-created_at")),
        )
        .get(pk=member_id)
    )
    if request.method == "GET":
        sub = next(iter(member.subscriptions.all()), None)
        magic = next(iter(member.magic_links.all()), None)
        return Response(
            {
                **member_admin_payload(member, request),
                "latestMagicLink": {"token": magic.token, "createdAt": magic.created_at.isoformat()} if magic else None,
                "subscriptionId": str(sub.id) if sub else None,
            }
        )
    if request.method == "DELETE":
        name = member.user.full_name
        email = member.user.email
        admin_name = request.user.full_name
        member.user.delete()
        log_audit("Member deleted", name, email, admin=admin_name)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = MemberUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user = member.user
    if "fullName" in data:
        user.full_name = data["fullName"]
    if "phone" in data:
        user.phone = data["phone"]
    if "email" in data:
        email = data["email"].strip().lower()
        if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
            raise ValidationError("A member with this email already exists.")
        user.email = email
    user.save()
    if "notes" in data:
        member.notes = data["notes"]
    if "photo" in data:
        member.photo = data["photo"]
    member.save()
    log_audit("Member edited", member.user.full_name, ", ".join(data.keys()), admin=request.user.full_name)
    return Response(member_admin_payload(member, request))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def member_status(request, member_id):
    member = MemberProfile.objects.select_related("user").get(pk=member_id)
    serializer = StatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    change_member_status(member, serializer.validated_data["status"], serializer.validated_data.get("reason", ""), request.user)
    return Response(member_admin_payload(member, request))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def member_magic_link(request, member_id):
    member = MemberProfile.objects.select_related("user").get(pk=member_id)
    link = create_magic_link(member, admin=request.user)
    return Response({"email": member.user.email, "token": link.token})
