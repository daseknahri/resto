import re

from django.utils.text import slugify
from rest_framework import serializers

from .models import Category, Dish, DishOption, TableLink


_LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$")


def _normalize_locale(value) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return ""
    if len(raw) >= 2 and re.match(r"^[a-z]{2}(?:-[a-z]{2})?$", raw):
        return raw
    if len(raw) >= 2 and re.match(r"^[a-z]{2}-[a-z]{4,}$", raw):
        return raw[:2]
    return ""


class LocalizedContentMixin:
    def _tenant_max_languages(self) -> int:
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request is not None else None
        plan = getattr(tenant, "plan", None) if tenant is not None else None
        try:
            max_languages = int(getattr(plan, "max_languages", 1) or 1)
        except (TypeError, ValueError):
            max_languages = 1
        return max(max_languages, 1)

    def _validate_i18n_map(self, value, *, field_label: str, max_length: int):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(f"{field_label} translations must be a JSON object.")
        cleaned = {}
        for raw_locale, raw_text in value.items():
            locale = _normalize_locale(raw_locale)
            if not locale or not _LOCALE_RE.match(locale):
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
        if user is not None and getattr(user, "is_authenticated", False):
            # Keep owner/admin editing payloads in canonical base fields.
            # Public/anonymous menu responses remain locale-aware.
            return ""
        query_locale = _normalize_locale(request.query_params.get("lang", ""))
        if query_locale:
            return query_locale
        header = ""
        if hasattr(request, "headers"):
            header = str(request.headers.get("Accept-Language", "") or "")
        if not header:
            header = str(request.META.get("HTTP_ACCEPT_LANGUAGE", "") or "")
        for raw_part in header.split(","):
            token = raw_part.split(";", 1)[0].strip()
            candidate = _normalize_locale(token)
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


class DishOptionSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all(), write_only=True)

    class Meta:
        model = DishOption
        fields = ["id", "dish", "name", "name_i18n", "price_delta", "is_required", "max_select"]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 1:
            raise serializers.ValidationError("Option name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Option name must be 150 characters or fewer.")
        return cleaned

    def validate_name_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Option name", max_length=150)

    def validate_price_delta(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price delta must be zero or greater.")
        return value

    def validate_max_select(self, value):
        if value is None or value < 1:
            raise serializers.ValidationError("Max select must be at least 1.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        return data


class DishSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    options = DishOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Dish
        fields = [
            "id",
            "category",
            "name",
            "name_i18n",
            "slug",
            "description",
            "description_i18n",
            "price",
            "currency",
            "image_url",
            "position",
            "is_published",
            "options",
        ]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Dish name must be at least 2 characters.")
        return cleaned

    def validate_name_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Dish name", max_length=200)

    def validate_description(self, value):
        text = (value or "").strip()
        if len(text) > 1500:
            raise serializers.ValidationError("Description must be 1500 characters or fewer.")
        return text

    def validate_description_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Dish description", max_length=1500)

    def validate_price(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_currency(self, value):
        cleaned = (value or "").strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter code (for example, USD).")
        return cleaned

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        data["description"] = self._localized_text(data.get("description"), data.get("description_i18n"))
        return data


class CategorySerializer(LocalizedContentMixin, serializers.ModelSerializer):
    dishes = DishSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "name_i18n",
            "slug",
            "description",
            "description_i18n",
            "image_url",
            "position",
            "is_published",
            "dishes",
        ]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Category name must be at least 2 characters.")
        return cleaned

    def validate_name_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Category name", max_length=150)

    def validate_description(self, value):
        text = (value or "").strip()
        if len(text) > 1000:
            raise serializers.ValidationError("Description must be 1000 characters or fewer.")
        return text

    def validate_description_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Category description", max_length=1000)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        data["description"] = self._localized_text(data.get("description"), data.get("description_i18n"))
        return data


class TableLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableLink
        fields = [
            "id",
            "label",
            "slug",
            "position",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
        }

    def validate_label(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 1:
            raise serializers.ValidationError("Table label is required.")
        if len(cleaned) > 40:
            raise serializers.ValidationError("Table label must be 40 characters or fewer.")
        return cleaned

    def validate_slug(self, value):
        cleaned = slugify((value or "").strip())
        if not cleaned:
            raise serializers.ValidationError("Slug must contain letters or numbers.")
        return cleaned[:55]

    def _resolve_unique_slug(self, base_slug: str, instance_id=None) -> str:
        base = (base_slug or "table").strip("-") or "table"
        base = base[:55]
        for idx in range(1, 300):
            suffix = "" if idx == 1 else f"-{idx}"
            candidate = f"{base[: max(55 - len(suffix), 1)]}{suffix}"
            exists = TableLink.objects.filter(slug=candidate)
            if instance_id is not None:
                exists = exists.exclude(pk=instance_id)
            if not exists.exists():
                return candidate
        raise serializers.ValidationError({"slug": "Unable to generate unique slug."})

    def create(self, validated_data):
        requested = validated_data.pop("slug", "")
        base = requested or slugify(validated_data.get("label", "")) or "table"
        validated_data["slug"] = self._resolve_unique_slug(base_slug=base)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        requested = validated_data.get("slug")
        if requested is not None:
            validated_data["slug"] = self._resolve_unique_slug(base_slug=requested, instance_id=instance.id)
        elif "label" in validated_data and validated_data["label"] != instance.label and not instance.slug:
            base = slugify(validated_data["label"]) or "table"
            validated_data["slug"] = self._resolve_unique_slug(base_slug=base, instance_id=instance.id)
        return super().update(instance, validated_data)
