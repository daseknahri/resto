from rest_framework import serializers
from django.utils.text import slugify

from .models import Category, Dish, DishOption, TableLink


class DishOptionSerializer(serializers.ModelSerializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all(), write_only=True)

    class Meta:
        model = DishOption
        fields = ["id", "dish", "name", "price_delta", "is_required", "max_select"]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 1:
            raise serializers.ValidationError("Option name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Option name must be 150 characters or fewer.")
        return cleaned

    def validate_price_delta(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price delta must be zero or greater.")
        return value

    def validate_max_select(self, value):
        if value is None or value < 1:
            raise serializers.ValidationError("Max select must be at least 1.")
        return value


class DishSerializer(serializers.ModelSerializer):
    options = DishOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Dish
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "description",
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

    def validate_description(self, value):
        text = (value or "").strip()
        if len(text) > 1500:
            raise serializers.ValidationError("Description must be 1500 characters or fewer.")
        return text

    def validate_price(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_currency(self, value):
        cleaned = (value or "").strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter code (for example, USD).")
        return cleaned


class CategorySerializer(serializers.ModelSerializer):
    dishes = DishSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
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

    def validate_description(self, value):
        text = (value or "").strip()
        if len(text) > 1000:
            raise serializers.ValidationError("Description must be 1000 characters or fewer.")
        return text


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
