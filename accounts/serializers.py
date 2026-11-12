from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from accounts.models import MemberProfile, User, UserRole
from spacez_backend.serialize import fmt_date, fmt_dt, iso_id, media_url


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    remember = serializers.BooleanField(required=False, default=True)


class MagicLinkSerializer(serializers.Serializer):
    token = serializers.CharField()


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RefreshSerializer(TokenRefreshSerializer):
    pass


def admin_user_payload(user: User) -> dict:
    return {
        "id": iso_id(user.id),
        "name": user.full_name,
        "email": user.email,
        "role": user.role,
        "phone": user.phone,
    }


def member_user_payload(profile: MemberProfile, request=None) -> dict:
    user = profile.user
    return {
        "id": iso_id(profile.id),
        "fullName": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "spaceType": profile.space_type,
        "accountStatus": profile.account_status,
        "photoUrl": media_url(request, profile.photo),
        "onboardingCompleted": profile.onboarding_completed,
        "memberSince": fmt_date(profile.created_at),
    }


def member_admin_payload(profile: MemberProfile, request=None) -> dict:
    user = profile.user
    magic = next(iter(profile.magic_links.all()), None)
    return {
        "id": iso_id(profile.id),
        "fullName": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "spaceType": profile.space_type,
        "accountStatus": profile.account_status,
        "photoUrl": media_url(request, profile.photo),
        "proofType": profile.proof_type,
        "proofNumber": profile.proof_number,
        "proofFileName": profile.proof_file_name,
        "proofUrl": media_url(request, profile.proof_document),
        "notes": profile.notes,
        "createdAt": fmt_date(profile.created_at),
        "onboardingCompleted": profile.onboarding_completed,
        "latestMagicLink": (
            {"token": magic.token, "memberId": iso_id(profile.id), "createdAt": fmt_dt(magic.created_at)}
            if magic
            else None
        ),
    }


class MemberWriteSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField()
    spaceType = serializers.CharField()
    proofType = serializers.CharField()
    proofNumber = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    photo = serializers.ImageField(required=False, allow_null=True)
    proofDocument = serializers.FileField(required=False, allow_null=True)


class MemberUpdateSerializer(serializers.Serializer):
    fullName = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ACTIVE", "INACTIVE", "SUSPENDED"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class OnboardingSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=6)
    photo = serializers.ImageField(required=False, allow_null=True)


class ProfileUpdateSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False)
    photo = serializers.ImageField(required=False, allow_null=True)
    password = serializers.CharField(required=False, min_length=6)


class AdminProfileSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
