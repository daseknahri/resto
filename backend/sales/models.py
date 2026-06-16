import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from tenancy.models import Plan, Tenant


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        NO_SHOW = "no_show", "No-show"  # reservation: confirmed guest didn't turn up
        PAID = "paid", "Paid"
        PROVISIONING = "provisioning", "Provisioning"
        LIVE = "live", "Live"

    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    booked_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the customer wants to come in (date + time combined). Populated on reservation submission.",
    )
    party_size = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of guests in the reservation.",
    )
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of when the pre-reservation reminder was sent to the customer. Null = not yet sent.",
    )
    # Unguessable token emailed to the customer so they can view/cancel their own
    # reservation without an account (bookings are anonymous). Set only for reservations.
    cancel_token = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"], name="lead_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


class ReservationTimelineEvent(models.Model):
    class Actions(models.TextChoices):
        NOTE = "note", "Note"
        STATUS_CHANGE = "status_change", "Status change"
        BULK_STATUS_CHANGE = "bulk_status_change", "Bulk status change"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="timeline_events")
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservation_timeline_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_timeline_events",
    )
    action = models.CharField(max_length=32, choices=Actions.choices, default=Actions.NOTE)
    note = models.TextField(blank=True)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.lead_id}:{self.action}"


class ReservationReminder(models.Model):
    class Channels(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"

    class Statuses(models.TextChoices):
        SENT = "sent", "Sent"
        OPENED = "opened", "Opened"
        FAILED = "failed", "Failed"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="reminders")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_reminders",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_reminders",
    )
    channel = models.CharField(max_length=20, choices=Channels.choices, default=Channels.WHATSAPP)
    status = models.CharField(max_length=20, choices=Statuses.choices, default=Statuses.SENT, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    whatsapp_link = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"Reminder {self.id} for lead {self.lead_id} ({self.status})"


class Deal(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="deals")
    amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=20, default="open")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deal for {self.lead.name}"


class Subscription(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant.slug} -> {self.plan.code}"


class TierUpgradeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELED = "canceled", "Canceled"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="tier_upgrade_requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tier_upgrade_requests",
    )
    current_plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="tier_upgrade_requests_from",
    )
    target_plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="tier_upgrade_requests_to",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_method = models.CharField(max_length=24, default="cash")
    payment_reference = models.CharField(max_length=120, blank=True)
    invoice_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount paid for this upgrade (set by admin when approving). Used to generate the invoice PDF.",
    )
    invoice_currency = models.CharField(
        max_length=8,
        default="USD",
        blank=True,
        help_text="Currency code for the invoice amount (e.g. USD, EUR, MAD).",
    )
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_tier_upgrade_requests",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant",),
                condition=models.Q(status="pending"),
                name="unique_pending_tier_upgrade_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.tenant.slug}: {self.current_plan.code} -> {self.target_plan.code} ({self.status})"


class ProvisioningJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def append_log(self, message: str):
        self.log = (self.log or "") + f"[{timezone.now().isoformat()}] {message}\n"
        self.save(update_fields=["log", "updated_at"])

    def __str__(self):
        return f"Provisioning {self.id} ({self.status})"


class ActivationToken(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="activation_tokens")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activation_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, tenant, user, hours_valid: int = 24):
        return cls.objects.create(
            tenant=tenant,
            user=user,
            token=secrets.token_hex(24),
            expires_at=timezone.now() + timedelta(hours=hours_valid),
        )

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at

    def __str__(self):
        return f"Activation for {self.user.email} ({self.tenant.slug})"


class AdminAuditLog(models.Model):
    class Actions(models.TextChoices):
        LEAD_PROVISIONED = "lead_provisioned", "Lead provisioned"
        ACTIVATION_RESENT = "activation_resent", "Activation resent"
        ONBOARDING_PACKAGE_SENT = "onboarding_package_sent", "Onboarding package sent"
        TENANT_SETTINGS_EXPORTED = "tenant_settings_exported", "Tenant settings exported"
        TENANT_SETTINGS_IMPORTED = "tenant_settings_imported", "Tenant settings imported"
        TENANT_SETTINGS_IMPORT_DRY_RUN = "tenant_settings_import_dry_run", "Tenant settings import dry-run"
        TIER_UPGRADE_REQUESTED = "tier_upgrade_requested", "Tier upgrade requested"
        TIER_UPGRADE_APPROVED = "tier_upgrade_approved", "Tier upgrade approved"
        TIER_UPGRADE_REJECTED = "tier_upgrade_rejected", "Tier upgrade rejected"
        LEAD_ARCHIVED = "lead_archived", "Lead archived"
        USER_ROLE_CHANGED = "user_role_changed", "User role changed"
        TENANT_DEACTIVATED = "tenant_deactivated", "Tenant deactivated"
        TENANT_REACTIVATED = "tenant_reactivated", "Tenant reactivated"
        # Money + policy actions performed from the admin console (audited for compliance).
        WALLET_BONUS_ISSUED = "wallet_bonus_issued", "Wallet bonus issued"
        TENANT_FLOAT_FUNDED = "tenant_float_funded", "Tenant float funded"
        CUSTOMER_WALLET_CREDITED = "customer_wallet_credited", "Customer wallet credited"
        VOUCHER_ISSUED = "voucher_issued", "Wallet voucher issued"
        DRIVER_APPROVED = "driver_approved", "Driver approved"
        DRIVER_REJECTED = "driver_rejected", "Driver rejected"
        DRIVER_PAYOUT_RECORDED = "driver_payout_recorded", "Driver payout recorded"
        PLATFORM_SETTINGS_UPDATED = "platform_settings_updated", "Platform settings updated"
        TENANT_LIVE_ORDERS_VIEWED = "tenant_live_orders_viewed", "Tenant live orders viewed"
        # OPS-5b additions
        CUSTOMER_PII_VIEWED = "customer_pii_viewed", "Customer PII viewed"
        CUSTOMER_DRIVER_TOGGLED = "customer_driver_toggled", "Customer driver toggled"
        DELIVERY_JOB_CREATED = "delivery_job_created", "Delivery job created"
        TENANT_DELETION_REQUESTED = "tenant_deletion_requested", "Tenant deletion requested"
        PLAN_FEATURE_FLAGS_UPDATED = "plan_feature_flags_updated", "Plan feature flags updated"
        # OPS-5c item 2: ride admin PII audit
        RIDE_PII_VIEWED = "ride_pii_viewed", "Ride PII viewed"
        CAR_DOCS_VIEWED = "car_docs_viewed", "Car docs viewed"
        # R18: GDPR customer PII erasure
        CUSTOMER_ERASED = "customer_erased", "Customer PII erased"

    action = models.CharField(max_length=64, choices=Actions.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_audit_logs")
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_audit_logs")
    target_repr = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        actor = self.actor.username if self.actor else "system"
        return f"{self.action} by {actor}"
