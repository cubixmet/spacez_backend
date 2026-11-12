import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class SpaceType(models.TextChoices):
    COWORKING = "Co-working", "Co-working"
    STUDENT = "Student", "Student"


class AccountStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"


class UserRole(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super admin"
    STAFF = "STAFF", "Staff"
    MEMBER = "MEMBER", "Member"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", UserRole.SUPER_ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("full_name", extra.get("full_name") or "Space Z Admin")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.MEMBER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def is_admin_role(self):
        return self.role in {UserRole.SUPER_ADMIN, UserRole.STAFF}


class MemberProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="member_profile")
    space_type = models.CharField(max_length=20, choices=SpaceType.choices)
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        help_text="Independent of billing status. ACTIVE + DUE members can still use the PWA.",
    )
    photo = models.ImageField(upload_to="members/photos/", blank=True, null=True)
    proof_type = models.CharField(max_length=64, blank=True)
    proof_number = models.CharField(max_length=64, blank=True)
    proof_document = models.FileField(upload_to="members/proofs/", blank=True, null=True)
    notes = models.TextField(blank=True)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "user__full_name"]

    def __str__(self):
        return self.user.full_name

    @property
    def photo_url(self):
        return self.photo.url if self.photo else None

    @property
    def proof_file_name(self):
        if not self.proof_document:
            return None
        return self.proof_document.name.rsplit("/", 1)[-1]


class MagicLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="magic_links")
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Magic link for {self.member}"
