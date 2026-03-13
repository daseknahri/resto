from urllib.parse import urlparse

from django.core.exceptions import DisallowedHost
from rest_framework import serializers
from django.utils import timezone

from .models import Plan, Profile, Tenant
from .tiering import external_plan_code, plan_display_name, plan_entitlements

SUPPORTED_PROFILE_LANGUAGES = {"en", "fr", "ar"}


def _normalize_local_media_url(value: str, request) -> str:
    raw = str(value or "").strip()
    if not raw or request is None:
        return raw

    parsed = urlparse(raw)
    try:
        request_host = str(getattr(request, "get_host", lambda: "")() or "").strip().lower()
    except DisallowedHost:
        request_host = str(getattr(request, "META", {}).get("HTTP_HOST", "") or "").strip().lower()
    if not request_host:
        return raw

    if parsed.scheme and parsed.netloc:
        parsed_host = parsed.netloc.strip().lower()
        if parsed.scheme == "http" and parsed_host == request_host and parsed.path.startswith("/media/"):
            return f"https://{request_host}{parsed.path}{f'?{parsed.query}' if parsed.query else ''}"
        return raw

    if raw.startswith("/media/"):
        scheme = "https" if request.is_secure() else "http"
        return f"{scheme}://{request_host}{raw}"

    return raw


class PlanSerializer(serializers.ModelSerializer):
    tier_code = serializers.SerializerMethodField()
    tier_name = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            "code",
            "name",
            "tier_code",
            "tier_name",
            "can_checkout",
            "can_whatsapp_order",
            "max_languages",
            "is_active",
        ]

    def get_tier_code(self, obj):
        return external_plan_code(getattr(obj, "code", ""))

    def get_tier_name(self, obj):
        return plan_display_name(getattr(obj, "code", ""), fallback=getattr(obj, "name", ""))


class ProfileSerializer(serializers.ModelSerializer):
    published_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "tagline",
            "description",
            "phone",
            "whatsapp",
            "address",
            "google_maps_url",
            "reservation_url",
            "facebook_url",
            "instagram_url",
            "tiktok_url",
            "primary_color",
            "secondary_color",
            "language",
            "logo_url",
            "hero_url",
            "is_open",
            "is_menu_temporarily_disabled",
            "menu_disabled_note",
            "is_menu_published",
            "published_at",
        ]

    def validate_phone(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        if len(digits) < 6:
            raise serializers.ValidationError("Phone number looks too short.")
        if any(ch for ch in cleaned if not (ch.isdigit() or ch in "+-() ")):
            raise serializers.ValidationError("Phone can only contain digits and + - ( ) characters.")
        return cleaned

    def validate_whatsapp(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        if len(digits) < 6:
            raise serializers.ValidationError("WhatsApp number looks too short.")
        if any(ch for ch in cleaned if not (ch.isdigit() or ch in "+-() ")):
            raise serializers.ValidationError("WhatsApp can only contain digits and + - ( ) characters.")
        return cleaned

    def validate_primary_color(self, value):
        color = (value or "").strip()
        if len(color) != 7 or not color.startswith("#"):
            raise serializers.ValidationError("Primary color must be a hex value like #0F766E.")
        try:
            int(color[1:], 16)
        except ValueError:
            raise serializers.ValidationError("Primary color must be a valid hex value.")
        return color.upper()

    def validate_secondary_color(self, value):
        color = (value or "").strip()
        if len(color) != 7 or not color.startswith("#"):
            raise serializers.ValidationError("Secondary color must be a hex value like #F59E0B.")
        try:
            int(color[1:], 16)
        except ValueError:
            raise serializers.ValidationError("Secondary color must be a valid hex value.")
        return color.upper()

    def validate_language(self, value):
        cleaned = (value or "").strip().lower()
        if not cleaned:
            return "en"
        primary = cleaned.split("-")[0]
        if primary not in SUPPORTED_PROFILE_LANGUAGES:
            raise serializers.ValidationError("Language must be one of: en, fr, ar.")
        return primary

    def validate(self, attrs):
        attrs = super().validate(attrs)
        disabled_in_payload = "is_menu_temporarily_disabled" in attrs
        note_in_payload = "menu_disabled_note" in attrs
        disabled_value = attrs.get(
            "is_menu_temporarily_disabled",
            self.instance.is_menu_temporarily_disabled if self.instance else False,
        )
        note_value = attrs.get(
            "menu_disabled_note",
            self.instance.menu_disabled_note if self.instance else "",
        )
        # Enforce disable-note only when disable/note fields are explicitly part of this update.
        if (disabled_in_payload or note_in_payload) and disabled_value and not (note_value or "").strip():
            raise serializers.ValidationError(
                {"menu_disabled_note": "Add a short message while menu is temporarily disabled."}
            )

        publish_value = attrs.get(
            "is_menu_published",
            self.instance.is_menu_published if self.instance else False,
        )
        if publish_value:
            from menu.models import Category, Dish

            category_count = Category.objects.filter(is_published=True).count()
            dish_count = Dish.objects.filter(is_published=True, category__is_published=True).count()
            if category_count < 1 or dish_count < 1:
                raise serializers.ValidationError(
                    {
                        "is_menu_published": (
                            "Add at least 1 published category and 1 published dish before publishing."
                        )
                    }
                )
        return attrs

    def update(self, instance, validated_data):
        previous = instance.is_menu_published
        instance = super().update(instance, validated_data)
        if not instance.is_menu_temporarily_disabled and instance.menu_disabled_note:
            instance.menu_disabled_note = ""
            instance.save(update_fields=["menu_disabled_note"])
        if instance.is_menu_published and (not previous or instance.published_at is None):
            instance.published_at = timezone.now()
            instance.save(update_fields=["published_at"])
        if not instance.is_menu_published and instance.published_at is not None:
            instance.published_at = None
            instance.save(update_fields=["published_at"])
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        data["logo_url"] = _normalize_local_media_url(data.get("logo_url", ""), request)
        data["hero_url"] = _normalize_local_media_url(data.get("hero_url", ""), request)
        return data


class TenantMetaSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    plan = PlanSerializer()
    profile = ProfileSerializer(allow_null=True)
    entitlements = serializers.DictField()
    feature_flags = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    @staticmethod
    def from_tenant(tenant: Tenant, *, request=None):
        plan_flags = []
        if getattr(tenant, "plan", None) and hasattr(tenant.plan, "feature_flags"):
            plan_flags = [
                {"key": f.key, "enabled": f.enabled, "config": f.config}
                for f in tenant.plan.feature_flags.all()
            ]
        profile = None
        if hasattr(tenant, "profile"):
            profile = ProfileSerializer(instance=tenant.profile, context={"request": request}).data
        return TenantMetaSerializer(
            {
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan,
                "profile": profile,
                "entitlements": plan_entitlements(tenant.plan) if getattr(tenant, "plan", None) else {},
                "feature_flags": plan_flags,
            },
            context={"request": request},
        )
