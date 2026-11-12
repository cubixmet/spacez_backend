from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from accounts.models import MagicLink, MemberProfile, User


class SpaceZUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "phone", "role")


class SpaceZUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "phone",
            "role",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = SpaceZUserChangeForm
    add_form = SpaceZUserCreationForm
    ordering = ["email"]
    list_display = ["email", "full_name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "full_name", "phone"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "phone", "role", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "space_type", "account_status", "onboarding_completed", "created_at"]
    list_filter = ["space_type", "account_status", "onboarding_completed"]
    search_fields = ["user__full_name", "user__email", "user__phone"]


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ["member", "token", "created_at", "used_at"]
    search_fields = ["token", "member__user__email"]
    readonly_fields = ["token", "created_at", "used_at"]
