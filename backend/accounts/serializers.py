from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from sales.models import ActivationToken

from .models import PasswordResetToken

User = get_user_model()


class ActivationSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        token = attrs.get("token")
        try:
            activation = ActivationToken.objects.select_related("user", "tenant").get(token=token)
        except ActivationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
        if not activation.is_valid():
            raise serializers.ValidationError("Token expired or used")
        attrs["activation"] = activation
        return attrs

    def save(self, **kwargs):
        activation: ActivationToken = self.validated_data["activation"]
        password = self.validated_data["password"]
        user: User = activation.user
        user.set_password(password)
        user.is_active = True
        user.save()
        activation.mark_used()
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        if not identifier or not password:
            raise serializers.ValidationError("Username/email and password are required")

        user = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier))
            .order_by("id")
            .first()
        )
        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("Account is inactive")
        if getattr(user, "tenant_id", None) and not getattr(getattr(user, "tenant", None), "is_active", True):
            lifecycle = getattr(getattr(user, "tenant", None), "lifecycle_status", "suspended")
            raise serializers.ValidationError(f"Tenant is {lifecycle}. Contact support.")

        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        if not identifier:
            raise serializers.ValidationError("Username or email is required")
        attrs["identifier"] = identifier
        attrs["user"] = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier), is_active=True)
            .order_by("id")
            .first()
        )
        return attrs

    def save(self, **kwargs):
        user = self.validated_data.get("user")
        if user is None or not user.email:
            return None
        return PasswordResetToken.issue(user=user, hours_valid=2)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        token = attrs.get("token", "").strip()
        try:
            reset = PasswordResetToken.objects.select_related("user").get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
        if not reset.is_valid():
            raise serializers.ValidationError("Token expired or used")
        attrs["reset"] = reset
        return attrs

    def save(self, **kwargs):
        reset: PasswordResetToken = self.validated_data["reset"]
        password = self.validated_data["password"]
        user = reset.user
        user.set_password(password)
        user.save(update_fields=["password"])
        reset.mark_used()
        return user
