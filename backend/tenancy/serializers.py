import re
from urllib.parse import urlparse

from django.core.exceptions import DisallowedHost
from rest_framework import serializers
from django.utils import timezone

from .models import Plan, Profile, Tenant
from .tiering import external_plan_code, plan_display_name, plan_entitlements

SUPPORTED_PROFILE_LANGUAGES = {"en", "fr", "ar"}
_LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$")
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_BUSINESS_HOURS_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


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


class LocalizedProfileContentMixin:
    def _force_locale_enabled(self) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        query_params = getattr(request, "query_params", None)
        if query_params is None:
            query_params = getattr(request, "GET", {})
        raw = str(query_params.get("force_locale", "") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _tenant_max_languages(self) -> int:
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request is not None else None
        plan = getattr(tenant, "plan", None) if tenant is not None else None
        try:
            max_languages = int(getattr(plan, "max_languages", 1) or 1)
        except (TypeError, ValueError):
            max_languages = 1
        return max(max_languages, 1)

    def _normalize_locale(self, value) -> str:
        cleaned = str(value or "").strip().lower().replace("_", "-")
        if not cleaned:
            return ""
        primary = cleaned.split("-", 1)[0]
        if primary not in SUPPORTED_PROFILE_LANGUAGES:
            return ""
        if _LOCALE_RE.match(cleaned):
            return cleaned
        return primary

    def _validate_i18n_map(self, value, *, field_label: str, max_length: int):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(f"{field_label} translations must be a JSON object.")

        cleaned = {}
        for raw_locale, raw_text in value.items():
            locale = self._normalize_locale(raw_locale)
            if not locale:
                raise serializers.ValidationError(
                    f"{field_label} translation locale must be like 'en', 'fr', or 'ar'."
                )
            text = str(raw_text or "").strip()
            if not text:
                continue
            if len(text) > max_length:
                raise serializers.ValidationError(
                    f"{field_label} translation for '{locale}' must be {max_length} characters or fewer."
                )
            cleaned[locale] = text

        max_languages = self._tenant_max_languages()
        if len(cleaned) > max_languages:
            raise serializers.ValidationError(
                f"Current plan supports up to {max_languages} translated language entries for {field_label}."
            )
        return cleaned

    def _request_locale(self) -> str:
        request = self.context.get("request")
        if request is None:
            return ""

        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and not self._force_locale_enabled()
        ):
            # Keep owner/admin editing payloads in canonical base fields.
            return ""

        query_params = getattr(request, "query_params", None)
        if query_params is None:
            query_params = getattr(request, "GET", {})

        query_locale = self._normalize_locale(query_params.get("lang", ""))
        if query_locale:
            return query_locale

        header = ""
        if hasattr(request, "headers"):
            header = str(request.headers.get("Accept-Language", "") or "")
        if not header:
            header = str(request.META.get("HTTP_ACCEPT_LANGUAGE", "") or "")

        for raw_part in header.split(","):
            token = raw_part.split(";", 1)[0].strip()
            candidate = self._normalize_locale(token)
            if candidate:
                return candidate
        return ""

    def _localized_text(self, base_value: str, translations):
        base = str(base_value or "")
        if not isinstance(translations, dict) or not translations:
            return base

        locale = self._request_locale()
        candidates = []
        if locale:
            candidates.append(locale)
            if "-" in locale:
                candidates.append(locale.split("-", 1)[0])

        for candidate in candidates:
            resolved = str(translations.get(candidate, "") or "").strip()
            if resolved:
                return resolved

        if base.strip():
            return base

        for key in sorted(translations.keys()):
            resolved = str(translations.get(key, "") or "").strip()
            if resolved:
                return resolved
        return base


class ProfileSerializer(LocalizedProfileContentMixin, serializers.ModelSerializer):
    published_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "tagline",
            "tagline_i18n",
            "description",
            "description_i18n",
            "business_hours",
            "business_hours_i18n",
            "business_hours_schedule",
            "phone",
            "whatsapp",
            "address",
            "address_i18n",
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

    def validate_tagline_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Tagline", max_length=150)

    def validate_address_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Address", max_length=255)

    def validate_description_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Description", max_length=2000)

    def validate_business_hours_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Business hours", max_length=1000)

    def validate_business_hours_schedule(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Business hours schedule must be a JSON object.")

        cleaned = {}
        for raw_day, raw_entry in value.items():
            day = str(raw_day or "").strip().lower()
            if day not in _BUSINESS_HOURS_DAYS:
                raise serializers.ValidationError(
                    f"Business hours day must be one of: {', '.join(_BUSINESS_HOURS_DAYS)}."
                )
            if not isinstance(raw_entry, dict):
                raise serializers.ValidationError("Business hours day entry must be an object.")

            enabled = bool(raw_entry.get("enabled", False))
            open_time = str(raw_entry.get("open", "") or "").strip()
            close_time = str(raw_entry.get("close", "") or "").strip()

            if enabled:
                if not _TIME_RE.match(open_time):
                    raise serializers.ValidationError(f"Opening time for '{day}' must use HH:MM format.")
                if not _TIME_RE.match(close_time):
                    raise serializers.ValidationError(f"Closing time for '{day}' must use HH:MM format.")
                if open_time == close_time:
                    raise serializers.ValidationError(
                        f"Opening and closing times for '{day}' cannot be the same."
                    )

            cleaned[day] = {
                "enabled": enabled,
                "open": open_time if enabled else "",
                "close": close_time if enabled else "",
            }

        return cleaned

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
        data["tagline"] = self._localized_text(data.get("tagline", ""), data.get("tagline_i18n"))
        data["address"] = self._localized_text(data.get("address", ""), data.get("address_i18n"))
        data["description"] = self._localized_text(data.get("description", ""), data.get("description_i18n"))
        data["business_hours"] = self._localized_text(
            data.get("business_hours", ""),
            data.get("business_hours_i18n"),
        )
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
