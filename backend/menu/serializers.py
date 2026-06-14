import re
from urllib.parse import urlparse

from django.utils.text import slugify
from rest_framework import serializers

from .models import Category, ComboComponent, Dish, DishOption, HappyHour, OptionGroup, SuperCategory, TableLink


_LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$")


def _normalize_local_media_url(value: str, request) -> str:
    raw = str(value or "").strip()
    if not raw or request is None:
        return raw

    parsed = urlparse(raw)
    request_host = str(getattr(request, "get_host", lambda: "")() or "").strip().lower()
    if not request_host:
        return raw

    if parsed.scheme and parsed.netloc:
        parsed_host = parsed.netloc.strip().lower()
        if parsed.scheme == "http" and parsed_host == request_host and parsed.path.startswith("/media/"):
            suffix = f"?{parsed.query}" if parsed.query else ""
            return f"https://{request_host}{parsed.path}{suffix}"
        return raw

    if raw.startswith("/media/"):
        scheme = "https" if request.is_secure() else "http"
        return f"{scheme}://{request_host}{raw}"

    return raw


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
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and not self._force_locale_enabled()
        ):
            return ""
        query_params = getattr(request, "query_params", None)
        if query_params is None:
            query_params = getattr(request, "GET", {})
        query_locale = _normalize_locale(query_params.get("lang", ""))
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


class SuperCategorySerializer(LocalizedContentMixin, serializers.ModelSerializer):
    category_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SuperCategory
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
            "is_temporarily_disabled",
            "disabled_note",
            "category_count",
        ]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Menu section name must be at least 2 characters.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Menu section name must be 150 characters or fewer.")
        return cleaned

    def validate_name_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Menu section name", max_length=150)

    def validate_disabled_note(self, value):
        text = (value or "").strip()
        if len(text) > 180:
            raise serializers.ValidationError("Disabled note must be 180 characters or fewer.")
        return text

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        return data


class DishOptionSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all(), write_only=True)
    group = serializers.PrimaryKeyRelatedField(
        queryset=OptionGroup.objects.all(), write_only=False, allow_null=True, required=False
    )

    class Meta:
        model = DishOption
        fields = ["id", "dish", "group", "name", "name_i18n", "price_delta", "is_required", "max_select", "position"]

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


class OptionInGroupSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    class Meta:
        model = DishOption
        fields = ["id", "name", "name_i18n", "price_delta", "position"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        return data


class OptionGroupSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    options = OptionInGroupSerializer(many=True, read_only=True)
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all(), write_only=True)

    class Meta:
        model = OptionGroup
        fields = ["id", "dish", "name", "name_i18n", "min_select", "max_select", "position", "options"]

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if len(cleaned) < 1:
            raise serializers.ValidationError("Group name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Group name must be 150 characters or fewer.")
        return cleaned

    def validate_name_i18n(self, value):
        return self._validate_i18n_map(value, field_label="Group name", max_length=150)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        return data


class DishSerializer(LocalizedContentMixin, serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    option_groups = OptionGroupSerializer(many=True, read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    category_name = serializers.SerializerMethodField()
    super_category_slug = serializers.CharField(source="category.super_category.slug", read_only=True)
    super_category_name = serializers.SerializerMethodField()
    tags = serializers.JSONField(default=list, required=False)
    allergens = serializers.JSONField(default=list, required=False)
    attributes = serializers.JSONField(default=dict, required=False)
    is_schedule_available = serializers.SerializerMethodField()
    # Combo fields.
    # Read: combo_components -> [{component_id, name, qty, position}] via SerializerMethodField.
    # Write: combo_components key in payload is extracted in to_internal_value and stored in
    #   validated_data["_combo_components_write"] so create/update can act on it.
    combo_components = serializers.SerializerMethodField()
    is_combo = serializers.SerializerMethodField()
    combo_unavailable = serializers.SerializerMethodField()
    # Happy-hour pricing fields — always present in customer-facing payloads.
    # context["happy_hours"] must be a list of active HappyHour rules (computed once
    # per request by the viewset and passed via get_serializer_context).  When the
    # key is absent (e.g. owner-admin reads) effective_price falls back to dish.price
    # and happy_hour is null — no per-dish N+1 query is ever issued.
    effective_price = serializers.SerializerMethodField()
    happy_hour = serializers.SerializerMethodField()

    class Meta:
        model = Dish
        fields = [
            "id",
            "category",
            "category_slug",
            "category_name",
            "super_category_slug",
            "super_category_name",
            "name",
            "name_i18n",
            "slug",
            "description",
            "description_i18n",
            "price",
            "effective_price",
            "happy_hour",
            "currency",
            "image_url",
            "tags",
            "allergens",
            "attributes",
            "position",
            "is_published",
            "is_available",
            "stock_qty",
            "low_stock_threshold",
            "availability_schedule",
            "is_schedule_available",
            "options",
            "option_groups",
            "is_combo",
            "combo_unavailable",
            "combo_components",
        ]

    def get_options(self, instance):
        ungrouped = [opt for opt in instance.options.all() if opt.group_id is None]
        return DishOptionSerializer(ungrouped, many=True, context=self.context).data

    def get_effective_price(self, instance) -> str:
        """Effective unit price after the best active happy-hour discount (string decimal).

        Falls back to dish.price when no happy_hours context is provided (owner reads)
        so that no N+1 DB query is ever issued per dish.
        """
        active_rules = self.context.get("happy_hours")
        if active_rules is None:
            return str(instance.price)
        from .pricing import effective_unit_price
        price, _ = effective_unit_price(instance, active_rules)
        return str(price)

    def get_happy_hour(self, instance) -> dict | None:
        """Active happy-hour metadata for this dish, or null when none applies."""
        active_rules = self.context.get("happy_hours")
        if active_rules is None:
            return None
        from .pricing import effective_unit_price, happy_hour_payload
        _, rule = effective_unit_price(instance, active_rules)
        return happy_hour_payload(rule)

    def get_is_schedule_available(self, obj) -> bool | None:
        """
        Returns True/False based on the availability_schedule, or None if no
        schedule is configured (meaning the dish is always available by schedule).
        """
        schedule = getattr(obj, "availability_schedule", None)
        if not schedule or not isinstance(schedule, dict):
            return None

        from datetime import datetime as _dt
        _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        now = _dt.utcnow()

        # Day restriction
        days = schedule.get("days")
        if days and isinstance(days, list) and len(days) > 0:
            if _WDAY[now.weekday()] not in days:
                return False

        # Time restriction
        time_start = str(schedule.get("time_start") or "").strip()
        time_end = str(schedule.get("time_end") or "").strip()
        if time_start and time_end:
            try:
                sh, sm = (int(p) for p in time_start.split(":")[:2])
                eh, em = (int(p) for p in time_end.split(":")[:2])
                now_m = now.hour * 60 + now.minute
                start_m = sh * 60 + sm
                end_m = eh * 60 + em
                if end_m <= start_m:
                    # Overnight window (e.g. 22:00 – 02:00)
                    if not (now_m >= start_m or now_m < end_m):
                        return False
                else:
                    if not (start_m <= now_m < end_m):
                        return False
            except (ValueError, TypeError):
                pass

        return True

    def get_combo_components(self, instance) -> list:
        """Read shape: [{component_id, name, qty, position}].

        Relies on combo_components being prefetched with select_related("component").
        Call the queryset with .prefetch_related("combo_components__component") for
        efficient reads.
        """
        try:
            components = instance.combo_components.all()
        except Exception:
            return []
        return [
            {
                "component_id": cc.component_id,
                "name": cc.component.name,
                "qty": cc.qty,
                "position": cc.position,
            }
            for cc in components
        ]

    def get_is_combo(self, instance) -> bool:
        """True when the dish has at least one combo component."""
        try:
            comps = instance.combo_components.all()
            return len(comps) > 0
        except Exception:
            return False

    def get_combo_unavailable(self, instance) -> bool:
        """True when ANY component is unavailable (is_available=False) or has
        finite stock that is zero. Cheap when combo_components__component is prefetched."""
        try:
            comps = instance.combo_components.all()
            if not comps:
                return False
            for cc in comps:
                comp = cc.component
                if not comp.is_available:
                    return True
                if comp.stock_qty is not None and comp.stock_qty <= 0:
                    return True
            return False
        except Exception:
            return False

    def validate_combo_components(self, value):
        """Write shape: [{component_id, qty}]. At most 8 components.

        Validates:
        - Each component_id references an existing, published Dish.
        - No component is itself a combo (no nesting).
        - No component is the dish itself (self-reference).
        - Max 8 components.

        This validator is called only when combo_components is present in the
        write payload; it does NOT replace the DB set on its own — that happens
        in update()/create().
        """
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("combo_components must be a list.")
        if len(value) > 8:
            raise serializers.ValidationError("A combo may have at most 8 components.")

        cleaned = []
        seen_ids = set()
        # Collect all referenced component_ids so we can fetch in one query.
        component_ids = []
        raw_entries = []
        for idx, entry in enumerate(value):
            if not isinstance(entry, dict):
                raise serializers.ValidationError(f"combo_components[{idx}] must be an object.")
            try:
                component_id = int(entry["component_id"])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(f"combo_components[{idx}].component_id is required and must be an integer.")
            try:
                qty = int(entry.get("qty", 1))
                if qty < 1:
                    raise ValueError
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"combo_components[{idx}].qty must be a positive integer.")
            if component_id in seen_ids:
                raise serializers.ValidationError(f"Duplicate component_id {component_id} in combo_components.")
            seen_ids.add(component_id)
            component_ids.append(component_id)
            raw_entries.append({"component_id": component_id, "qty": qty})

        if not component_ids:
            return []

        # Self-reference check (instance.pk is None on create — no self-ref possible)
        instance = self.instance
        if instance is not None and instance.pk in seen_ids:
            raise serializers.ValidationError("A dish cannot be a component of itself.")

        # Reverse-nesting check: a dish that is already a component of another
        # combo may not become a combo itself (would nest retroactively — the
        # forward check below only blocks adding an existing combo AS a component).
        if instance is not None and instance.pk is not None:
            try:
                first_parent = instance.part_of_combos.select_related("dish").first()
            except Exception:
                first_parent = None
            if first_parent is not None:
                raise serializers.ValidationError(
                    f"This dish is a component of combo '{first_parent.dish.name}'. "
                    "A component cannot itself become a combo (nested combos are not allowed)."
                )

        # Fetch all referenced dishes in one query
        dishes = {d.pk: d for d in Dish.objects.filter(pk__in=component_ids).prefetch_related("combo_components")}

        for entry in raw_entries:
            cid = entry["component_id"]
            if cid not in dishes:
                raise serializers.ValidationError(f"Component dish id={cid} does not exist.")
            comp = dishes[cid]
            if not comp.is_published:
                raise serializers.ValidationError(f"Component '{comp.name}' (id={cid}) is not published.")
            # No nesting — component must not itself be a combo
            if comp.combo_components.exists():
                raise serializers.ValidationError(
                    f"Component '{comp.name}' (id={cid}) is itself a combo. Nested combos are not allowed."
                )
            cleaned.append(entry)

        return cleaned

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

    def validate_tags(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        seen = set()
        cleaned = []
        for item in value:
            tag = str(item).strip().lower()[:32]
            if tag and tag not in seen:
                seen.add(tag)
                cleaned.append(tag)
        return cleaned

    def validate_allergens(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Allergens must be a list.")
        allowed = {
            "gluten", "crustaceans", "eggs", "fish", "peanuts", "soy",
            "milk", "tree_nuts", "celery", "mustard", "sesame",
            "sulphites", "lupin", "molluscs",
        }
        seen = set()
        cleaned = []
        for item in value:
            key = str(item).strip().lower()[:32]
            if key in allowed and key not in seen:
                seen.add(key)
                cleaned.append(key)
        return cleaned

    def validate_attributes(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("attributes must be an object.")
        _ALLOWED = {
            "sku": 64,
            "barcode": 64,
            "brand": 80,
            "unit": 40,
        }
        cleaned = {}
        for key, raw in value.items():
            if key not in _ALLOWED:
                # Silently drop unknown keys per spec.
                continue
            if isinstance(raw, (list, dict)):
                raise serializers.ValidationError(
                    f"attributes['{key}'] must be a string, not a list or object."
                )
            text = str(raw).strip() if raw is not None else ""
            if not text:
                # Drop empty/whitespace values.
                continue
            max_len = _ALLOWED[key]
            if len(text) > max_len:
                raise serializers.ValidationError(
                    f"attributes['{key}'] must be {max_len} characters or fewer."
                )
            cleaned[key] = text
        return cleaned

    def validate_currency(self, value):
        cleaned = (value or "").strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter code (for example, USD).")
        return cleaned

    def validate_stock_qty(self, value):
        # null = unlimited; any positive integer is valid
        if value is None:
            return None
        if value < 0:
            raise serializers.ValidationError("Stock quantity must be zero or greater.")
        return value

    def get_category_name(self, instance):
        category = getattr(instance, "category", None)
        if category is None:
            return ""
        return self._localized_text(category.name, category.name_i18n)

    def get_super_category_name(self, instance):
        super_category = getattr(getattr(instance, "category", None), "super_category", None)
        if super_category is None:
            return ""
        return self._localized_text(super_category.name, super_category.name_i18n)

    def to_internal_value(self, data):
        """Extract combo_components from the write payload before standard field
        validation so we can validate it ourselves and pass it to create/update."""
        # Pop before DRF processes fields (combo_components is a read-only
        # SerializerMethodField so DRF ignores it in writes by default).
        raw_combo = data.get("combo_components")  # may be absent
        result = super().to_internal_value(data)
        if "combo_components" in data:
            # validate_combo_components handles all validation; store in private key.
            validated = self.validate_combo_components(raw_combo)
            result["_combo_components_write"] = validated
        return result

    def _apply_combo_components(self, instance, entries: list):
        """Replace the combo_components set for this dish with the given validated entries.

        entries: [{component_id, qty}] — from validated_data["_combo_components_write"].
        Runs in whatever transaction the caller is in.
        """
        # Delete existing set, then bulk-create the new one.
        instance.combo_components.all().delete()
        for position, entry in enumerate(entries):
            ComboComponent.objects.create(
                dish=instance,
                component_id=entry["component_id"],
                qty=entry["qty"],
                position=position,
            )

    def create(self, validated_data):
        combo_entries = validated_data.pop("_combo_components_write", None)
        instance = super().create(validated_data)
        if combo_entries is not None:
            self._apply_combo_components(instance, combo_entries)
        return instance

    def update(self, instance, validated_data):
        combo_entries = validated_data.pop("_combo_components_write", None)
        instance = super().update(instance, validated_data)
        if combo_entries is not None:
            self._apply_combo_components(instance, combo_entries)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        data["description"] = self._localized_text(data.get("description"), data.get("description_i18n"))
        data["image_url"] = _normalize_local_media_url(data.get("image_url", ""), self.context.get("request"))
        return data


class CategorySerializer(LocalizedContentMixin, serializers.ModelSerializer):
    dishes = DishSerializer(many=True, read_only=True)
    super_category_slug = serializers.CharField(source="super_category.slug", read_only=True)
    super_category_name = serializers.SerializerMethodField()
    # dish_count is derived from the already-prefetched `dishes` relation so it
    # never issues an extra query.  The SPA uses it to show how many dishes will
    # be cascade-deleted when a category is removed.
    dish_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "super_category",
            "super_category_slug",
            "super_category_name",
            "name",
            "name_i18n",
            "slug",
            "description",
            "description_i18n",
            "image_url",
            "position",
            "is_published",
            "is_temporarily_disabled",
            "course",
            "dish_count",
            "dishes",
        ]

    def validate_course(self, value):
        if value is None:
            return 0
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("course must be an integer between 0 and 4.")
        if v < 0 or v > 4:
            raise serializers.ValidationError("course must be between 0 (no course) and 4.")
        return v

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

    def get_super_category_name(self, instance):
        super_category = getattr(instance, "super_category", None)
        if super_category is None:
            return ""
        return self._localized_text(super_category.name, super_category.name_i18n)

    def get_dish_count(self, instance):
        """Return the number of dishes in this category.

        Uses the prefetched `dishes` queryset when available (no extra DB hit);
        falls back to a direct count otherwise.  The SPA displays this count in
        the delete-confirmation dialog so the owner knows how many dishes will be
        cascade-deleted alongside the category.
        """
        dishes_prefetch = getattr(instance, "_prefetched_objects_cache", {}).get("dishes")
        if dishes_prefetch is not None:
            return len(dishes_prefetch)
        return instance.dishes.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = self._localized_text(data.get("name"), data.get("name_i18n"))
        data["description"] = self._localized_text(data.get("description"), data.get("description_i18n"))
        data["image_url"] = _normalize_local_media_url(data.get("image_url", ""), self.context.get("request"))
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
        # Single DB round-trip: fetch all slugs sharing the prefix, then check
        # candidates in memory instead of firing one query per iteration.
        qs = TableLink.objects.filter(slug__startswith=base)
        if instance_id is not None:
            qs = qs.exclude(pk=instance_id)
        existing = set(qs.values_list("slug", flat=True))
        for idx in range(1, 300):
            suffix = "" if idx == 1 else f"-{idx}"
            candidate = f"{base[: max(55 - len(suffix), 1)]}{suffix}"
            if candidate not in existing:
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


class HappyHourSerializer(serializers.ModelSerializer):
    """Owner-facing serializer for HappyHour CRUD.

    Validation rules (enforced here, not in the model):
    - name >= 2 chars.
    - days: non-empty list of unique ints in [0, 6].
    - percent_off: 1–90.
    - start_time != end_time.
    - At most 8 HappyHour rows per tenant on create.
    """

    category_ids = serializers.SerializerMethodField()

    class Meta:
        model = HappyHour
        fields = [
            "id",
            "name",
            "days",
            "start_time",
            "end_time",
            "percent_off",
            "category_ids",
            "is_active",
        ]

    def get_category_ids(self, instance) -> list:
        return list(instance.categories.values_list("id", flat=True))

    def to_internal_value(self, data):
        # Extract category_ids before DRF processes the rest (it is not a model field).
        self._category_ids_input = None
        if "category_ids" in data:
            self._category_ids_input = data.get("category_ids")
        return super().to_internal_value(data)

    def validate_name(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("name must be at least 2 characters.")
        return value

    def validate_days(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("days must be a non-empty list.")
        for d in value:
            if not isinstance(d, int) or d < 0 or d > 6:
                raise serializers.ValidationError("Each day must be an integer 0–6.")
        if len(set(value)) != len(value):
            raise serializers.ValidationError("days must not contain duplicates.")
        return value

    def validate_percent_off(self, value):
        if value < 1 or value > 90:
            raise serializers.ValidationError("percent_off must be between 1 and 90.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start is not None and end is not None and start == end:
            raise serializers.ValidationError(
                {"end_time": "start_time and end_time must differ."}
            )
        # Validate category_ids when provided.
        cat_ids = getattr(self, "_category_ids_input", None)
        if cat_ids is not None:
            if not isinstance(cat_ids, list):
                raise serializers.ValidationError({"category_ids": "category_ids must be a list."})
            from .models import Category as _Cat
            valid_ids = set(_Cat.objects.filter(id__in=cat_ids).values_list("id", flat=True))
            bad = [i for i in cat_ids if i not in valid_ids]
            if bad:
                raise serializers.ValidationError({"category_ids": f"Unknown category ids: {bad}."})
        return attrs

    def validate_create_limit(self):
        """Call on create only. Raises ValidationError when the tenant already has 8 rules."""
        if HappyHour.objects.count() >= 8:
            raise serializers.ValidationError(
                {"non_field_errors": "Maximum of 8 happy-hour rules allowed per tenant."}
            )

    def create(self, validated_data):
        self.validate_create_limit()
        cat_ids = getattr(self, "_category_ids_input", None) or []
        instance = super().create(validated_data)
        if cat_ids:
            from .models import Category as _Cat
            instance.categories.set(_Cat.objects.filter(id__in=cat_ids))
        return instance

    def update(self, instance, validated_data):
        cat_ids = getattr(self, "_category_ids_input", None)
        instance = super().update(instance, validated_data)
        if cat_ids is not None:
            from .models import Category as _Cat
            instance.categories.set(_Cat.objects.filter(id__in=cat_ids))
        return instance
