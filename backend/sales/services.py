import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context
from django.utils.text import slugify

from tenancy.models import Domain, Plan, Tenant
from tenancy.tiering import canonical_plan_code, external_plan_code, is_plan_upgrade
from .messaging import (
    build_activation_message,
    build_activation_url,
    build_admin_url,
    build_onboarding_url,
    build_public_menu_url,
    build_signin_url,
    build_tenant_frontend_url,
    build_workspace_url,
    send_activation_email,
    send_activation_whatsapp,
)
from .models import ActivationToken, Lead, ProvisioningJob, Subscription, TierUpgradeRequest

logger = logging.getLogger(__name__)
provisioning_logger = logging.getLogger("sales.provisioning")
SLUG_MAX_LENGTH = 50


@dataclass
class ProvisionResult:
    tenant: Tenant
    user: object
    job: ProvisioningJob
    activation_token: ActivationToken
    admin_url: str
    workspace_url: str
    signin_url: str
    tenant_url: str
    activation_url: str
    whatsapp_link: str
    whatsapp_message_template: str


@dataclass
class ActivationResendResult:
    tenant: Tenant
    user: object
    activation_token: ActivationToken
    admin_url: str
    workspace_url: str
    signin_url: str
    tenant_url: str
    activation_url: str
    whatsapp_link: str
    whatsapp_message_template: str


@dataclass
class OnboardingPackageResult:
    tenant: Tenant
    user: object
    activation_token: ActivationToken
    admin_url: str
    workspace_url: str
    signin_url: str
    tenant_url: str
    activation_url: str
    whatsapp_link: str
    whatsapp_message_template: str


@dataclass
class TierUpgradeDecisionResult:
    upgrade_request: TierUpgradeRequest
    tenant: Tenant
    previous_plan: Plan
    new_plan: Plan


def mask_secret(secret: str, keep_start: int = 6, keep_end: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= keep_start + keep_end:
        return "*" * len(secret)
    return f"{secret[:keep_start]}...{secret[-keep_end:]}"


def _log_provisioning_event(event: str, **fields):
    payload = {"event": event}
    payload.update(fields)
    provisioning_logger.info(event, extra={"structured": payload})


def issue_activation(tenant, user, phone: str = ""):
    activation = ActivationToken.issue(tenant=tenant, user=user)
    admin_url = build_admin_url(tenant)
    workspace_url = build_workspace_url(tenant)
    onboarding_url = build_onboarding_url(tenant)
    signin_url = build_signin_url(tenant)
    tenant_url = build_tenant_frontend_url(tenant)
    public_menu_url = build_public_menu_url(tenant)
    activation_url = build_activation_url(tenant, activation.token)
    whatsapp_message_template = build_activation_message(
        workspace_url,
        signin_url,
        activation_url,
        onboarding_url,
        public_menu_url,
        activation.token,
    )
    whatsapp_link = send_activation_whatsapp(
        phone,
        workspace_url,
        signin_url,
        activation_url,
        onboarding_url,
        public_menu_url,
        activation.token,
    )
    if getattr(user, "email", ""):
        try:
            send_activation_email(
                user.email,
                workspace_url,
                signin_url,
                activation_url,
                onboarding_url,
                public_menu_url,
                activation.token,
            )
        except Exception as exc:
            # Provisioning/onboarding must remain available even when SMTP is down.
            logger.exception("Activation email send failed", extra={"tenant_slug": getattr(tenant, "slug", "")})
            _log_provisioning_event(
                "activation_email_failed",
                tenant_id=getattr(tenant, "id", None),
                tenant_slug=getattr(tenant, "slug", ""),
                user_id=getattr(user, "id", None),
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
    return activation, admin_url, workspace_url, signin_url, tenant_url, activation_url, whatsapp_link, whatsapp_message_template


def _default_domain_suffix() -> str:
    configured_suffix = (getattr(settings, "TENANT_DOMAIN_SUFFIX", "") or "").strip().lower().lstrip(".")
    if configured_suffix:
        return configured_suffix

    base_url = (getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "").strip()
    if not base_url:
        return "localhost"
    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    host = (parsed.hostname or "").strip().lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or "localhost"


def _is_local_suffix(value: str) -> bool:
    raw = (value or "").strip().lower()
    return raw in {"localhost", "127.0.0.1"} or raw.endswith(".localhost")


def normalize_domain_suffix(domain_suffix: str | None) -> str:
    fallback = _default_domain_suffix()
    raw = (domain_suffix or "").strip().lower().lstrip(".")
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    if not raw:
        return fallback

    if _is_local_suffix(raw) and not _is_local_suffix(fallback):
        return fallback
    return raw


def _base_slug_for_lead(lead: Lead) -> str:
    source = ""
    if lead.email:
        source = lead.email.split("@")[0]
    elif lead.name:
        source = lead.name
    elif lead.phone:
        source = lead.phone

    base_slug = slugify(source)[:SLUG_MAX_LENGTH]
    if not base_slug:
        base_slug = f"tenant-{lead.id or 'new'}"
    return base_slug


def _build_next_slug(base_slug: str, index: int) -> str:
    if index <= 1:
        return base_slug[:SLUG_MAX_LENGTH]
    suffix = f"-{index}"
    trim = max(SLUG_MAX_LENGTH - len(suffix), 1)
    return f"{base_slug[:trim]}{suffix}"


def _availability(slug: str, domain_suffix: str) -> dict:
    domain = f"{slug}.{domain_suffix}"
    slug_available = not Tenant.objects.filter(slug=slug).exists()
    domain_available = not Domain.objects.filter(domain=domain).exists()
    return {
        "slug": slug,
        "domain": domain,
        "slug_available": slug_available,
        "domain_available": domain_available,
        "available": slug_available and domain_available,
    }


def preview_lead_provision(lead: Lead, domain_suffix: str = "localhost", requested_slug: str | None = None) -> dict:
    normalized_suffix = normalize_domain_suffix(domain_suffix)
    base_slug = slugify(requested_slug or "")[:SLUG_MAX_LENGTH] if requested_slug else _base_slug_for_lead(lead)
    if not base_slug:
        base_slug = _base_slug_for_lead(lead)

    # Shared models are stored in public schema.
    with schema_context(get_public_schema_name()):
        requested = _availability(base_slug, normalized_suffix)
        index = 1
        resolved = requested
        while not resolved["available"]:
            index += 1
            candidate = _build_next_slug(base_slug, index)
            resolved = _availability(candidate, normalized_suffix)

    return {
        "lead_id": lead.id,
        "domain_suffix": normalized_suffix,
        "input_slug": requested["slug"],
        "input_domain": requested["domain"],
        "input_slug_available": requested["slug_available"],
        "input_domain_available": requested["domain_available"],
        "input_available": requested["available"],
        "collision": not requested["available"],
        "resolved_slug": resolved["slug"],
        "resolved_domain": resolved["domain"],
    }


def provision_lead(lead: Lead, domain_suffix: str = "localhost", requested_slug: str | None = None) -> ProvisionResult:
    """Provision tenant, domain, owner, subscription for a lead."""
    User = get_user_model()
    _log_provisioning_event(
        "lead_provision_start",
        lead_id=lead.id,
        lead_status=getattr(lead, "status", None),
        requested_slug=(requested_slug or "").strip().lower() or None,
        domain_suffix=normalize_domain_suffix(domain_suffix),
    )

    # Tenant/domain writes are shared-data writes and must run in the public schema.
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            already_live = ProvisioningJob.objects.filter(
                lead=lead,
                status=ProvisioningJob.Status.SUCCESS,
                tenant__isnull=False,
            ).exists()
            if already_live:
                _log_provisioning_event("lead_provision_blocked", lead_id=lead.id, reason="already_provisioned")
                raise ValueError("Lead already provisioned. Use resend activation or package actions instead.")

            plan = lead.plan
            if plan is None:
                _log_provisioning_event("lead_provision_blocked", lead_id=lead.id, reason="plan_missing")
                raise ValueError("Lead has no plan selected. Assign a plan before provisioning.")
            if not getattr(plan, "is_active", True):
                _log_provisioning_event(
                    "lead_provision_blocked",
                    lead_id=lead.id,
                    reason="plan_inactive",
                    plan_code=getattr(plan, "code", ""),
                )
                raise ValueError(
                    f"Plan '{external_plan_code(plan.code)}' is not launched yet. Keep lead on waitlist or activate the plan first."
                )
            preview = preview_lead_provision(lead, domain_suffix=domain_suffix, requested_slug=requested_slug)
            slug = preview["resolved_slug"]
            domain_name = preview["resolved_domain"]

            if Tenant.objects.filter(slug=slug).exists() or Domain.objects.filter(domain=domain_name).exists():
                _log_provisioning_event(
                    "lead_provision_blocked",
                    lead_id=lead.id,
                    reason="slug_or_domain_taken",
                    slug=slug,
                    domain=domain_name,
                )
                raise ValueError("Tenant slug/domain is no longer available. Please retry provisioning.")

            tenant = Tenant.objects.create(
                slug=slug,
                schema_name=slug,
                name=lead.name or slug,
                plan=plan,
            )
            Domain.objects.create(domain=domain_name, tenant=tenant, is_primary=True)

            owner_email = lead.email or f"{slug}@example.com"
            user, created = User.objects.get_or_create(
                username=owner_email,
                defaults={
                    "email": owner_email,
                    "role": User.Roles.TENANT_OWNER,
                },
            )
            if created:
                user.set_password(User.objects.make_random_password())
            user.tenant = tenant
            user.save()

            Subscription.objects.get_or_create(tenant=tenant, plan=plan)

            (
                activation,
                admin_url,
                workspace_url,
                signin_url,
                tenant_url,
                activation_url,
                whatsapp_link,
                whatsapp_message_template,
            ) = issue_activation(tenant, user, phone=lead.phone)

            job = ProvisioningJob.objects.create(lead=lead, tenant=tenant, status=ProvisioningJob.Status.SUCCESS)
            job.append_log("Provisioning completed")
            job.append_log(f"Activation token: {mask_secret(activation.token)}")
            job.append_log(f"Workspace URL: {workspace_url}")
            job.append_log(f"Sign-in URL: {signin_url}")
            job.append_log(f"Django admin URL: {admin_url}")
            job.append_log(f"Activation URL: {activation_url}")
            if whatsapp_link:
                job.append_log(f"WhatsApp link: {whatsapp_link}")

            lead.status = Lead.Status.LIVE
            if lead.onboarded_at is None:
                lead.onboarded_at = timezone.now()
            lead.save(update_fields=["status", "onboarded_at", "updated_at"])

            logger.info("Provisioned tenant %s for lead %s", tenant.slug, lead.id)
            _log_provisioning_event(
                "lead_provision_success",
                lead_id=lead.id,
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                schema_name=tenant.schema_name,
                domain=domain_name,
                plan_code=getattr(plan, "code", ""),
                owner_user_id=getattr(user, "id", None),
                provisioning_job_id=job.id,
            )

    return ProvisionResult(
        tenant=tenant,
        user=user,
        job=job,
        activation_token=activation,
        admin_url=admin_url,
        workspace_url=workspace_url,
        signin_url=signin_url,
        tenant_url=tenant_url,
        activation_url=activation_url,
        whatsapp_link=whatsapp_link,
        whatsapp_message_template=whatsapp_message_template,
    )


def resend_activation_for_lead(lead: Lead) -> ActivationResendResult:
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            latest_job = _get_latest_provisioning_job(lead)
            tenant = latest_job.tenant
            user = _get_tenant_owner_user(tenant)

            (
                activation,
                admin_url,
                workspace_url,
                signin_url,
                tenant_url,
                activation_url,
                whatsapp_link,
                whatsapp_message_template,
            ) = issue_activation(tenant, user, phone=lead.phone)
            latest_job.append_log("Activation token resent")
            latest_job.append_log(f"Activation token: {mask_secret(activation.token)}")
            latest_job.append_log(f"Workspace URL: {workspace_url}")
            latest_job.append_log(f"Sign-in URL: {signin_url}")
            latest_job.append_log(f"Django admin URL: {admin_url}")
            latest_job.append_log(f"Activation URL: {activation_url}")
            if whatsapp_link:
                latest_job.append_log(f"WhatsApp link: {whatsapp_link}")
            _log_provisioning_event(
                "lead_activation_resent",
                lead_id=lead.id,
                tenant_id=getattr(tenant, "id", None),
                tenant_slug=getattr(tenant, "slug", ""),
                provisioning_job_id=getattr(latest_job, "id", None),
            )

    return ActivationResendResult(
        tenant=tenant,
        user=user,
        activation_token=activation,
        admin_url=admin_url,
        workspace_url=workspace_url,
        signin_url=signin_url,
        tenant_url=tenant_url,
        activation_url=activation_url,
        whatsapp_link=whatsapp_link,
        whatsapp_message_template=whatsapp_message_template,
    )


def _get_latest_provisioning_job(lead: Lead) -> ProvisioningJob:
    latest_job = (
        ProvisioningJob.objects.filter(lead=lead, status=ProvisioningJob.Status.SUCCESS, tenant__isnull=False)
        .select_related("tenant")
        .order_by("-created_at")
        .first()
    )
    if latest_job is None or latest_job.tenant is None:
        raise ValueError("No provisioned tenant found for this lead yet.")
    return latest_job


def _get_tenant_owner_user(tenant) -> object:
    User = get_user_model()
    user = tenant.users.filter(role=User.Roles.TENANT_OWNER).order_by("id").first()
    if user is None:
        user = tenant.users.order_by("id").first()
    if user is None:
        raise ValueError("No tenant user found for this lead.")
    return user


def _get_reusable_activation_token(user, tenant):
    return (
        ActivationToken.objects.filter(
            user=user,
            tenant=tenant,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )


def onboarding_package_for_lead(lead: Lead, refresh_token: bool = False) -> OnboardingPackageResult:
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            latest_job = _get_latest_provisioning_job(lead)
            tenant = latest_job.tenant
            user = _get_tenant_owner_user(tenant)

            token_obj = None if refresh_token else _get_reusable_activation_token(user, tenant)
            if token_obj is None:
                (
                    token_obj,
                    admin_url,
                    workspace_url,
                    signin_url,
                    tenant_url,
                    activation_url,
                    whatsapp_link,
                    whatsapp_message_template,
                ) = issue_activation(tenant, user, phone=lead.phone)
                latest_job.append_log("Onboarding package token issued")
                latest_job.append_log(f"Activation token: {mask_secret(token_obj.token)}")
            else:
                admin_url = build_admin_url(tenant)
                workspace_url = build_workspace_url(tenant)
                onboarding_url = build_onboarding_url(tenant)
                signin_url = build_signin_url(tenant)
                tenant_url = build_tenant_frontend_url(tenant)
                public_menu_url = build_public_menu_url(tenant)
                activation_url = build_activation_url(tenant, token_obj.token)
                whatsapp_message_template = build_activation_message(
                    workspace_url,
                    signin_url,
                    activation_url,
                    onboarding_url,
                    public_menu_url,
                    token_obj.token,
                )
                whatsapp_link = send_activation_whatsapp(
                    lead.phone,
                    workspace_url,
                    signin_url,
                    activation_url,
                    onboarding_url,
                    public_menu_url,
                    token_obj.token,
                )

            latest_job.append_log("Onboarding package prepared")
            latest_job.append_log(f"Workspace URL: {workspace_url}")
            latest_job.append_log(f"Sign-in URL: {signin_url}")
            latest_job.append_log(f"Django admin URL: {admin_url}")
            latest_job.append_log(f"Activation URL: {activation_url}")
            if whatsapp_link:
                latest_job.append_log(f"WhatsApp link: {whatsapp_link}")
            _log_provisioning_event(
                "lead_onboarding_package_prepared",
                lead_id=lead.id,
                tenant_id=getattr(tenant, "id", None),
                tenant_slug=getattr(tenant, "slug", ""),
                refreshed_token=bool(refresh_token),
                provisioning_job_id=getattr(latest_job, "id", None),
            )

    return OnboardingPackageResult(
        tenant=tenant,
        user=user,
        activation_token=token_obj,
        admin_url=admin_url,
        workspace_url=workspace_url,
        signin_url=signin_url,
        tenant_url=tenant_url,
        activation_url=activation_url,
        whatsapp_link=whatsapp_link,
        whatsapp_message_template=whatsapp_message_template,
    )


def create_tier_upgrade_request(
    *,
    tenant: Tenant,
    requester,
    target_plan_code: str,
    payment_method: str = "cash",
    payment_reference: str = "",
    customer_note: str = "",
) -> TierUpgradeRequest:
    if tenant is None:
        raise ValueError("Tenant not resolved.")

    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            tenant_obj = Tenant.objects.select_related("plan").get(pk=tenant.id)
            current_plan = tenant_obj.plan
            if current_plan is None:
                raise ValueError("Current tenant plan is missing.")

            canonical_target = canonical_plan_code(target_plan_code)
            try:
                target_plan = Plan.objects.get(code=canonical_target)
            except Plan.DoesNotExist as exc:
                raise ValueError("Target plan does not exist.") from exc

            if not is_plan_upgrade(getattr(current_plan, "code", ""), getattr(target_plan, "code", "")):
                raise ValueError("Target plan must be higher than current plan.")

            if TierUpgradeRequest.objects.filter(
                tenant=tenant_obj,
                status=TierUpgradeRequest.Status.PENDING,
            ).exists():
                raise ValueError("A pending upgrade request already exists for this tenant.")

            return TierUpgradeRequest.objects.create(
                tenant=tenant_obj,
                requester=requester if getattr(requester, "is_authenticated", False) else None,
                current_plan=current_plan,
                target_plan=target_plan,
                payment_method=(payment_method or "cash").strip().lower() or "cash",
                payment_reference=(payment_reference or "").strip(),
                customer_note=(customer_note or "").strip(),
            )


def decide_tier_upgrade_request(
    *,
    request_id: int,
    decision: str,
    actor,
    admin_note: str = "",
    payment_reference: str = "",
) -> TierUpgradeDecisionResult:
    normalized_decision = (decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("Decision must be 'approve' or 'reject'.")

    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            upgrade_request = (
                TierUpgradeRequest.objects.select_for_update()
                .select_related("tenant", "current_plan", "target_plan")
                .get(pk=request_id)
            )
            if upgrade_request.status != TierUpgradeRequest.Status.PENDING:
                raise ValueError("Upgrade request is already resolved.")

            tenant_obj = upgrade_request.tenant
            previous_plan = tenant_obj.plan
            target_plan = upgrade_request.target_plan

            if normalized_decision == "reject":
                upgrade_request.status = TierUpgradeRequest.Status.REJECTED
                upgrade_request.admin_note = (admin_note or "").strip()
                upgrade_request.approved_by = actor if getattr(actor, "is_authenticated", False) else None
                upgrade_request.decided_at = timezone.now()
                if payment_reference:
                    upgrade_request.payment_reference = payment_reference.strip()
                upgrade_request.save(
                    update_fields=[
                        "status",
                        "admin_note",
                        "approved_by",
                        "decided_at",
                        "payment_reference",
                        "updated_at",
                    ]
                )
                return TierUpgradeDecisionResult(
                    upgrade_request=upgrade_request,
                    tenant=tenant_obj,
                    previous_plan=previous_plan,
                    new_plan=previous_plan,
                )

            if not getattr(target_plan, "is_active", True):
                raise ValueError(
                    f"Plan '{external_plan_code(target_plan.code)}' is not launched yet. Activate this plan before approval."
                )

            if previous_plan and not is_plan_upgrade(getattr(previous_plan, "code", ""), getattr(target_plan, "code", "")):
                raise ValueError("Tenant plan already matches or exceeds this target tier.")

            tenant_obj.plan = target_plan
            tenant_obj.save(update_fields=["plan"])

            today = timezone.now().date()
            Subscription.objects.filter(tenant=tenant_obj, status="active").exclude(plan=target_plan).update(
                status="ended",
                end_date=today,
            )
            Subscription.objects.update_or_create(
                tenant=tenant_obj,
                plan=target_plan,
                defaults={
                    "status": "active",
                    "start_date": today,
                    "end_date": None,
                },
            )

            upgrade_request.status = TierUpgradeRequest.Status.APPROVED
            upgrade_request.admin_note = (admin_note or "").strip()
            if payment_reference:
                upgrade_request.payment_reference = payment_reference.strip()
            upgrade_request.approved_by = actor if getattr(actor, "is_authenticated", False) else None
            upgrade_request.decided_at = timezone.now()
            upgrade_request.save(
                update_fields=[
                    "status",
                    "admin_note",
                    "payment_reference",
                    "approved_by",
                    "decided_at",
                    "updated_at",
                ]
            )

            return TierUpgradeDecisionResult(
                upgrade_request=upgrade_request,
                tenant=tenant_obj,
                previous_plan=previous_plan,
                new_plan=target_plan,
            )
