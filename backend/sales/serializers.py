from django.utils import timezone
from rest_framework import serializers

from tenancy.models import Plan, Tenant
from tenancy.tiering import (
    canonical_plan_code,
    external_plan_code,
    is_valid_plan_feature_flag_key,
    is_plan_upgrade,
    normalize_plan_feature_flag_key,
    plan_display_name,
    plan_entitlements,
    plan_feature_flag_catalog,
)

from .models import AdminAuditLog, Lead, ProvisioningJob, ReservationReminder, ReservationTimelineEvent, TierUpgradeRequest
from .sla import reservation_sla_snapshot


class ReservationSlaSerializerMixin:
    def _reservation_sla(self, obj):
        now = self.context.get("_reservation_sla_now")
        if now is None:
            now = timezone.now()
            self.context["_reservation_sla_now"] = now
        return reservation_sla_snapshot(
            source=getattr(obj, "source", ""),
            status=getattr(obj, "status", ""),
            created_at=getattr(obj, "created_at", None),
            now=now,
        )

    def get_follow_up_due_at(self, obj):
        return self._reservation_sla(obj)["follow_up_due_at"]

    def get_sla_state(self, obj):
        return self._reservation_sla(obj)["sla_state"]

    def get_sla_minutes_overdue(self, obj):
        return self._reservation_sla(obj)["sla_minutes_overdue"]


class ReservationReminderStatsSerializerMixin:
    def get_last_reminder_status(self, obj):
        return getattr(obj, "last_reminder_status", "") or ""

    def get_last_reminder_at(self, obj):
        return getattr(obj, "last_reminder_at", None)

    def _safe_count(self, obj, attr_name: str):
        value = getattr(obj, attr_name, 0)
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def get_reminder_count(self, obj):
        return self._safe_count(obj, "reminder_count")

    def get_reminder_opened_count(self, obj):
        return self._safe_count(obj, "reminder_opened_count")

    def get_reminder_failed_count(self, obj):
        return self._safe_count(obj, "reminder_failed_count")


class LeadSerializer(ReservationSlaSerializerMixin, ReservationReminderStatsSerializerMixin, serializers.ModelSerializer):
    plan_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    hp = serializers.CharField(write_only=True, required=False, allow_blank=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    follow_up_due_at = serializers.SerializerMethodField()
    sla_state = serializers.SerializerMethodField()
    sla_minutes_overdue = serializers.SerializerMethodField()
    last_reminder_status = serializers.SerializerMethodField()
    last_reminder_at = serializers.SerializerMethodField()
    reminder_count = serializers.SerializerMethodField()
    reminder_opened_count = serializers.SerializerMethodField()
    reminder_failed_count = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "source",
            "notes",
            "tenant_slug",
            "status",
            "plan_code",
            "archived_at",
            "onboarded_at",
            "hp",
            "created_at",
            "follow_up_due_at",
            "sla_state",
            "sla_minutes_overdue",
            "last_reminder_status",
            "last_reminder_at",
            "reminder_count",
            "reminder_opened_count",
            "reminder_failed_count",
        ]
        read_only_fields = ("status", "archived_at", "onboarded_at", "created_at")

    def validate(self, attrs):
        if attrs.get("hp"):
            raise serializers.ValidationError("Invalid submission")
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("Email or phone is required")

        raw_plan_code = attrs.pop("plan_code", None)
        if raw_plan_code not in (None, ""):
            canonical = canonical_plan_code(raw_plan_code)
            try:
                attrs["plan"] = Plan.objects.get(code=canonical)
            except Plan.DoesNotExist as exc:
                raise serializers.ValidationError({"plan_code": "Invalid plan selection"}) from exc

        attrs.pop("hp", None)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["plan_code"] = external_plan_code(getattr(getattr(instance, "plan", None), "code", "")) or ""
        return data


class OwnerReservationSerializer(ReservationSlaSerializerMixin, ReservationReminderStatsSerializerMixin, serializers.ModelSerializer):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    follow_up_due_at = serializers.SerializerMethodField()
    sla_state = serializers.SerializerMethodField()
    sla_minutes_overdue = serializers.SerializerMethodField()
    last_reminder_status = serializers.SerializerMethodField()
    last_reminder_at = serializers.SerializerMethodField()
    reminder_count = serializers.SerializerMethodField()
    reminder_opened_count = serializers.SerializerMethodField()
    reminder_failed_count = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "source",
            "status",
            "notes",
            "tenant_slug",
            "created_at",
            "updated_at",
            "follow_up_due_at",
            "sla_state",
            "sla_minutes_overdue",
            "last_reminder_status",
            "last_reminder_at",
            "reminder_count",
            "reminder_opened_count",
            "reminder_failed_count",
        ]
        read_only_fields = fields


class OwnerReservationUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            Lead.Status.NEW,
            Lead.Status.CONTACTED,
            Lead.Status.WON,
            Lead.Status.LOST,
        )
    )


class OwnerReservationBulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=200)
    status = serializers.ChoiceField(
        choices=(
            Lead.Status.NEW,
            Lead.Status.CONTACTED,
            Lead.Status.WON,
            Lead.Status.LOST,
        )
    )

    def validate_ids(self, value):
        deduped = []
        seen = set()
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        if not deduped:
            raise serializers.ValidationError("At least one reservation id is required.")
        return deduped


class OwnerReservationBulkReminderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=200)
    require_failed_last_reminder = serializers.BooleanField(required=False, default=False)

    def validate_ids(self, value):
        deduped = []
        seen = set()
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        if not deduped:
            raise serializers.ValidationError("At least one reservation id is required.")
        return deduped


class ReservationTimelineEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = ReservationTimelineEvent
        fields = [
            "id",
            "action",
            "note",
            "previous_status",
            "new_status",
            "actor_username",
            "created_at",
        ]
        read_only_fields = fields


class ReservationTimelineCreateSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=1500, allow_blank=False)


class ReservationReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationReminder
        fields = [
            "id",
            "channel",
            "status",
            "phone",
            "message",
            "whatsapp_link",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReservationReminderResultSerializer(serializers.Serializer):
    reminder_id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(
        choices=(
            ReservationReminder.Statuses.OPENED,
            ReservationReminder.Statuses.FAILED,
        )
    )
    error = serializers.CharField(required=False, allow_blank=True, max_length=255)


class OwnerReservationBulkReminderResultItemSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField(min_value=1)
    reminder_id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(
        choices=(
            ReservationReminder.Statuses.OPENED,
            ReservationReminder.Statuses.FAILED,
        )
    )
    error = serializers.CharField(required=False, allow_blank=True, max_length=255)


class OwnerReservationBulkReminderResultSerializer(serializers.Serializer):
    items = OwnerReservationBulkReminderResultItemSerializer(many=True, allow_empty=False, max_length=200)


class ProvisioningJobSerializer(serializers.ModelSerializer):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    lead_name = serializers.CharField(source="lead.name", read_only=True)

    class Meta:
        model = ProvisioningJob
        fields = ["id", "lead_name", "tenant_slug", "status", "log", "created_at", "updated_at"]


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    lead_name = serializers.CharField(source="lead.name", read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            "id",
            "action",
            "actor_username",
            "tenant_slug",
            "lead_name",
            "target_repr",
            "ip_address",
            "metadata",
            "created_at",
        ]


class AdminTenantSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    plan_code = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    primary_domain = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "schema_name",
            "is_active",
            "lifecycle_status",
            "suspended_at",
            "canceled_at",
            "canceled_reason",
            "owner_username",
            "plan_code",
            "plan_name",
            "primary_domain",
        ]

    def get_plan_code(self, obj):
        return external_plan_code(getattr(getattr(obj, "plan", None), "code", ""))

    def get_plan_name(self, obj):
        plan = getattr(obj, "plan", None)
        return plan_display_name(getattr(plan, "code", ""), fallback=getattr(plan, "name", ""))

    def get_primary_domain(self, obj):
        annotated = getattr(obj, "primary_domain_value", None)
        if annotated is not None:
            return str(annotated or "")
        domains = getattr(obj, "domains", None)
        if domains is None:
            return ""
        primary = domains.filter(is_primary=True).first()
        if primary:
            return getattr(primary, "domain", "") or ""
        fallback = domains.order_by("id").first()
        return getattr(fallback, "domain", "") if fallback else ""


class TenantLifecycleUpdateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("suspend", "reactivate", "cancel"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        action = attrs.get("action")
        reason = (attrs.get("reason") or "").strip()
        if action == "cancel" and not reason:
            raise serializers.ValidationError({"reason": "Cancel action requires a reason."})
        attrs["reason"] = reason
        return attrs


class AdminPlanFeatureFlagItemSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    enabled = serializers.BooleanField()
    config = serializers.JSONField(required=False, allow_null=True)

    def validate_key(self, value):
        normalized = normalize_plan_feature_flag_key(value)
        if not normalized:
            raise serializers.ValidationError("Feature flag key is required.")
        if not is_valid_plan_feature_flag_key(normalized):
            raise serializers.ValidationError("Unknown feature flag key.")
        return normalized

    def validate_config(self, value):
        if value is None:
            return None
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError("Feature flag config must be an object or array.")
        return value


class AdminPlanFeatureFlagUpdateSerializer(serializers.Serializer):
    feature_flags = AdminPlanFeatureFlagItemSerializer(many=True, allow_empty=False, max_length=100)

    def validate_feature_flags(self, value):
        deduped = []
        seen = set()
        for row in value:
            key = row["key"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        if not deduped:
            raise serializers.ValidationError("At least one feature flag update is required.")
        return deduped


class AdminPlanFeatureFlagPlanSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    plan_tier_code = serializers.CharField()
    plan_tier_name = serializers.CharField()
    plan_is_active = serializers.BooleanField()
    feature_flags = serializers.ListField(child=serializers.DictField())

    @staticmethod
    def from_plan(plan: Plan, *, flags=None):
        catalog_rows = plan_feature_flag_catalog()
        catalog_by_key = {row["key"]: row for row in catalog_rows}

        flags = flags or []
        existing = {}
        for item in flags:
            key = normalize_plan_feature_flag_key(getattr(item, "key", ""))
            if not key:
                continue
            existing[key] = {
                "enabled": bool(getattr(item, "enabled", False)),
                "config": getattr(item, "config", None),
            }

        rendered_flags = []
        for catalog_item in catalog_rows:
            key = catalog_item["key"]
            state = existing.get(key, {"enabled": False, "config": None})
            rendered_flags.append(
                {
                    "key": key,
                    "label": catalog_item.get("label", key.replace("_", " ").title()),
                    "description": catalog_item.get("description", ""),
                    "enabled": bool(state.get("enabled", False)),
                    "config": state.get("config"),
                }
            )

        # Keep unknown keys visible for support/debugging even if no longer cataloged.
        for key in sorted(existing.keys()):
            if key in catalog_by_key:
                continue
            state = existing[key]
            rendered_flags.append(
                {
                    "key": key,
                    "label": key.replace("_", " ").title(),
                    "description": "Custom legacy flag",
                    "enabled": bool(state.get("enabled", False)),
                    "config": state.get("config"),
                }
            )

        return {
            "plan_code": external_plan_code(getattr(plan, "code", "")),
            "plan_name": getattr(plan, "name", ""),
            "plan_tier_code": external_plan_code(getattr(plan, "code", "")),
            "plan_tier_name": plan_display_name(getattr(plan, "code", ""), fallback=getattr(plan, "name", "")),
            "plan_is_active": bool(getattr(plan, "is_active", True)),
            "feature_flags": rendered_flags,
        }


class TierUpgradeRequestSerializer(serializers.ModelSerializer):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    requester_username = serializers.CharField(source="requester.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)
    current_plan_code = serializers.SerializerMethodField()
    current_plan_name = serializers.SerializerMethodField()
    target_plan_code = serializers.SerializerMethodField()
    target_plan_name = serializers.SerializerMethodField()
    target_plan_is_active = serializers.BooleanField(source="target_plan.is_active", read_only=True)

    class Meta:
        model = TierUpgradeRequest
        fields = [
            "id",
            "tenant_slug",
            "status",
            "current_plan_code",
            "current_plan_name",
            "target_plan_code",
            "target_plan_name",
            "target_plan_is_active",
            "payment_method",
            "payment_reference",
            "customer_note",
            "admin_note",
            "requester_username",
            "approved_by_username",
            "requested_at",
            "decided_at",
            "updated_at",
        ]

    def get_current_plan_code(self, obj):
        return external_plan_code(getattr(getattr(obj, "current_plan", None), "code", ""))

    def get_current_plan_name(self, obj):
        plan = getattr(obj, "current_plan", None)
        return plan_display_name(getattr(plan, "code", ""), fallback=getattr(plan, "name", ""))

    def get_target_plan_code(self, obj):
        return external_plan_code(getattr(getattr(obj, "target_plan", None), "code", ""))

    def get_target_plan_name(self, obj):
        plan = getattr(obj, "target_plan", None)
        return plan_display_name(getattr(plan, "code", ""), fallback=getattr(plan, "name", ""))


class TierUpgradeRequestCreateSerializer(serializers.Serializer):
    target_plan_code = serializers.CharField()
    payment_method = serializers.CharField(required=False, allow_blank=True, default="cash")
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=1500)

    def validate_target_plan_code(self, value):
        canonical = canonical_plan_code(value)
        try:
            plan = Plan.objects.get(code=canonical)
        except Plan.DoesNotExist as exc:
            raise serializers.ValidationError("Invalid plan selection.") from exc
        return plan

    def validate_payment_method(self, value):
        method = (value or "cash").strip().lower()
        if method not in {"cash", "bank_transfer", "other"}:
            raise serializers.ValidationError("Unsupported payment method.")
        return method

    def validate(self, attrs):
        tenant = self.context.get("tenant")
        current_plan = getattr(tenant, "plan", None)
        target_plan = attrs.get("target_plan_code")
        if target_plan is None:
            raise serializers.ValidationError({"target_plan_code": "Target plan is required."})
        if current_plan is None:
            raise serializers.ValidationError("Current tenant plan is missing.")
        if not is_plan_upgrade(getattr(current_plan, "code", ""), getattr(target_plan, "code", "")):
            raise serializers.ValidationError(
                {"target_plan_code": "Target plan must be a higher tier than your current plan."}
            )
        attrs["target_plan"] = target_plan
        attrs.pop("target_plan_code", None)
        return attrs


class TierUpgradeDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("approve", "reject"))
    admin_note = serializers.CharField(required=False, allow_blank=True, max_length=1500)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)


class TierUpgradeTargetSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()
    ordering_mode = serializers.CharField()
    can_order = serializers.BooleanField()
    can_checkout = serializers.BooleanField()
    can_whatsapp_order = serializers.BooleanField()
    max_languages = serializers.IntegerField()
    can_request = serializers.BooleanField()

    @staticmethod
    def from_plan(plan: Plan, *, can_request: bool = True):
        entitlements = plan_entitlements(plan)
        return {
            "code": entitlements["tier_code"],
            "name": entitlements["tier_name"],
            "is_active": entitlements["is_active"],
            "ordering_mode": entitlements["ordering_mode"],
            "can_order": entitlements["can_order"],
            "can_checkout": entitlements["can_checkout"],
            "can_whatsapp_order": entitlements["can_whatsapp_order"],
            "max_languages": entitlements["max_languages"],
            "can_request": bool(can_request),
        }
