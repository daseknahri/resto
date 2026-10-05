import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections, transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_database_alias,
    schema_context,
    schema_exists,
)
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
from .models import (
    ActivationToken,
    Lead,
    ProvisioningJob,
    Subscription,
    TierUpgradeRequest,
    account_is_activated,
)
from .redaction import mask_secret, mask_token_in

logger = logging.getLogger(__name__)
provisioning_logger = logging.getLogger("sales.provisioning")
SLUG_MAX_LENGTH = 50
# Upper bound on "-2", "-3", ... candidates tried when resolving a free slug, so a
# pathological base can never spin the preview loop forever.
SLUG_MAX_ATTEMPTS = 500

# A RUNNING ProvisioningJob younger than this is an in-flight attempt and blocks a second
# provision of the same lead. Older ones are presumed dead (the HTTP worker that ran it
# was killed mid schema build — request timeouts are ~60s) and may be superseded.
PROVISIONING_STALE_AFTER = timedelta(minutes=15)

# The slug is BOTH the tenant's Postgres schema name and the leftmost DNS label of its
# domain, so it must never shadow a Postgres system schema or a platform/infra host
# (a lead `admin@…` or `menu@…` provisioned in one click would otherwise take over that
# host — the tenant middleware resolves Domain rows before the public-host fallback).
RESERVED_SLUGS = frozenset({
    "public",
    "www",
    "admin",
    "api",
    "app",
    "menu",
    "static",
    "media",
    "mail",
    "information_schema",
    "pg_catalog",
    "pg_toast",
})
# Postgres reserves the whole `pg_` namespace for system schemas.
RESERVED_SLUG_PREFIX = "pg_"

# The only schema names ever interpolated into DROP SCHEMA (and they are quoted too).
# Slugs are slugify() output — lowercase ASCII alphanumerics, "-" and "_" — so this
# admits every real tenant schema while excluding quotes, whitespace and dots.
_DROPPABLE_SCHEMA_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


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


class OwnerAlreadyActivatedError(ValueError):
    """The owner has already finished account setup (``account_is_activated``), so an
    activation link would only be rejected when clicked — refuse to issue/re-show one."""


def _log_provisioning_event(event: str, **fields):
    payload = {"event": event}
    payload.update(fields)
    provisioning_logger.info(event, extra={"structured": payload})


def _refuse_if_owner_activated(user, tenant) -> None:
    if account_is_activated(user):
        raise OwnerAlreadyActivatedError(
            "The owner has already activated this account, so an activation link would be rejected. "
            f"Ask them to sign in at {build_signin_url(tenant)} or use \"Forgot password\"."
        )


def _log_owner_links(
    job: ProvisioningJob,
    *,
    token: str,
    workspace_url: str,
    signin_url: str,
    admin_url: str,
    activation_url: str,
    whatsapp_link: str,
) -> None:
    """Append the owner's links to ``job.log`` with the activation token MASKED.

    The log is persisted and served to the admin console, so the raw token (which
    the activation URL and the WhatsApp link both embed) must never land in it.
    """
    job.append_log(f"Activation token: {mask_secret(token)}")
    job.append_log(f"Workspace URL: {workspace_url}")
    job.append_log(f"Sign-in URL: {signin_url}")
    job.append_log(f"Django admin URL: {admin_url}")
    job.append_log(f"Activation URL: {mask_token_in(activation_url, token)}")
    if whatsapp_link:
        job.append_log(f"WhatsApp link: {mask_token_in(whatsapp_link, token)}")


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


def _hostname_of(value: str) -> str:
    """Lower-cased hostname of a URL or bare host ("" when there is none)."""
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").strip().lower().strip(".")


def _default_domain_suffix() -> str:
    configured_suffix = (getattr(settings, "TENANT_DOMAIN_SUFFIX", "") or "").strip().lower().lstrip(".")
    if configured_suffix:
        return configured_suffix

    host = _hostname_of(getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "")
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


def is_reserved_slug(slug: str) -> bool:
    """True when ``slug`` may never become a tenant (system schema / platform host label)."""
    value = (slug or "").strip().lower()
    return (
        value in RESERVED_SLUGS
        or value == get_public_schema_name()
        or value.startswith(RESERVED_SLUG_PREFIX)
    )


def _platform_hosts() -> set[str]:
    """Hosts the platform itself serves — a tenant Domain must never equal one of them."""
    hosts = {_hostname_of(host) for host in (getattr(settings, "PUBLIC_SCHEMA_HOSTS", None) or [])}
    hosts.add(_hostname_of(getattr(settings, "BRAND_DOMAIN", "") or ""))
    hosts.add(_hostname_of(getattr(settings, "PUBLIC_MENU_BASE_URL", "") or ""))
    hosts.discard("")
    return hosts


def _unreserved_slug(slug: str) -> str:
    """The nearest non-reserved variant of ``slug`` (``admin`` -> ``admin-2``).

    A ``pg_`` prefix can't be fixed by appending a suffix, so it becomes ``pg-``.
    """
    if slug.startswith(RESERVED_SLUG_PREFIX):
        slug = "pg-" + slug[len(RESERVED_SLUG_PREFIX):]
    if is_reserved_slug(slug):
        slug = _build_next_slug(slug, 2)
    return slug


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
    # One-click provisioning must keep working for generic mailboxes (admin@, menu@…).
    return _unreserved_slug(base_slug)


def _build_next_slug(base_slug: str, index: int) -> str:
    if index <= 1:
        return base_slug[:SLUG_MAX_LENGTH]
    suffix = f"-{index}"
    trim = max(SLUG_MAX_LENGTH - len(suffix), 1)
    return f"{base_slug[:trim]}{suffix}"


def _availability(slug: str, domain_suffix: str) -> dict:
    domain = f"{slug}.{domain_suffix}"
    reserved = is_reserved_slug(slug) or domain.lower() in _platform_hosts()
    slug_available = not Tenant.objects.filter(slug=slug).exists()
    domain_available = not Domain.objects.filter(domain=domain).exists()
    # A stray Postgres schema (e.g. the orphan of a failed build) must BLOCK the slug,
    # never be adopted: create_schema(check_if_exists=True) would skip migrating it and
    # the "provisioned" tenant would 500 on every endpoint.
    schema_available = not schema_exists(slug)
    return {
        "slug": slug,
        "domain": domain,
        "reserved": reserved,
        "slug_available": slug_available,
        "domain_available": domain_available,
        "schema_available": schema_available,
        "available": not reserved and slug_available and domain_available and schema_available,
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
            if index > SLUG_MAX_ATTEMPTS:
                raise ValueError("Could not find an available tenant slug. Request a different slug.")
            candidate = _unreserved_slug(_build_next_slug(base_slug, index))
            resolved = _availability(candidate, normalized_suffix)

    return {
        "lead_id": lead.id,
        "domain_suffix": normalized_suffix,
        "input_slug": requested["slug"],
        "input_domain": requested["domain"],
        "input_reserved": requested["reserved"],
        "input_slug_available": requested["slug_available"],
        "input_domain_available": requested["domain_available"],
        "input_available": requested["available"],
        "collision": not requested["available"],
        "resolved_slug": resolved["slug"],
        "resolved_domain": resolved["domain"],
    }


def _lock_lead(lead: Lead) -> None:
    """Row-lock the lead for the rest of the caller's transaction."""
    try:
        Lead.objects.select_for_update().only("id").get(pk=lead.id)
    except Lead.DoesNotExist as exc:
        raise ValueError("Lead no longer exists.") from exc


def _block_or_supersede_running_jobs(lead: Lead) -> None:
    """Refuse while another provision of ``lead`` is in flight; retire dead attempts.

    Must run under the lead row lock (``_lock_lead``) so the check and the new RUNNING
    job it precedes are atomic with respect to a concurrent provision.
    """
    stale_before = timezone.now() - PROVISIONING_STALE_AFTER
    in_flight = ProvisioningJob.objects.filter(
        lead=lead,
        status=ProvisioningJob.Status.RUNNING,
        created_at__gte=stale_before,
    ).exists()
    if in_flight:
        _log_provisioning_event("lead_provision_blocked", lead_id=lead.id, reason="already_in_progress")
        raise ValueError(
            "Provisioning is already in progress for this lead. "
            "Wait a minute and refresh — do not provision it again."
        )

    stale_jobs = ProvisioningJob.objects.filter(
        lead=lead,
        status=ProvisioningJob.Status.RUNNING,
        created_at__lt=stale_before,
    )
    for stale in stale_jobs:
        # Its tenant row (and possibly a partial schema) is deliberately left in place
        # for ops review — dropping data on a timeout heuristic is not safe.
        stale.status = ProvisioningJob.Status.FAILED
        stale.append_log(
            f"Superseded: still RUNNING after {int(PROVISIONING_STALE_AFTER.total_seconds() // 60)} min "
            "(worker presumed dead). Tenant left in place for manual review."
        )
        stale.save(update_fields=["status", "updated_at"])
        _log_provisioning_event(
            "lead_provision_stale_job_superseded",
            lead_id=lead.id,
            provisioning_job_id=stale.id,
            tenant_id=getattr(stale, "tenant_id", None),
        )


def _assert_owner_account_reusable(user, lead: Lead, *, owner_role: str) -> None:
    """Refuse to re-parent an existing account onto a newly provisioned tenant.

    ``provision_lead`` keys the owner on the lead's email, so without this check a
    lead (incl. a public one) carrying an existing owner's email would silently move
    that owner off their restaurant, or attach a platform/staff account to a tenant.
    Multi-restaurant ownership is a future product decision; refusing is the safe default.
    """
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or getattr(user, "role", None) != owner_role
    ):
        raise ValueError(
            "This email belongs to a platform or staff account and cannot own a restaurant. "
            "Use a different email for this lead."
        )
    current_tenant_id = getattr(user, "tenant_id", None)
    if current_tenant_id is None:
        return
    # The one tenant it may be moved off: an earlier, never-live attempt for THIS lead
    # (e.g. a superseded stale RUNNING job whose tenant was left in place).
    abandoned_attempt_of_this_lead = (
        ProvisioningJob.objects.filter(lead=lead, tenant_id=current_tenant_id)
        .exclude(status=ProvisioningJob.Status.SUCCESS)
        .exists()
    )
    if abandoned_attempt_of_this_lead:
        return
    raise ValueError("This email already owns another restaurant — use a different email for this lead.")


def _drop_schema_created_by_attempt(schema_name: str) -> bool:
    """DROP a schema a failed provisioning attempt created. Returns True when dropped.

    The name comes from the slug, so it is validated against a strict pattern AND
    quoted before interpolation; reserved/system names are never dropped.
    """
    if not _DROPPABLE_SCHEMA_NAME_RE.fullmatch(schema_name or "") or is_reserved_slug(schema_name):
        logger.error("Refusing to drop schema with unexpected name %r", schema_name)
        return False
    try:
        conn = connections[get_tenant_database_alias()]
        conn.set_schema_to_public()
        with conn.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {conn.ops.quote_name(schema_name)} CASCADE")
    except Exception:
        logger.exception("Could not drop partially-built schema %s", schema_name)
        return False
    _log_provisioning_event("lead_provision_schema_dropped", schema_name=schema_name)
    return True


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
            # Serialize provisions of the same lead: a second click / admin action
            # waits here until the first one's phase 1 commits, then sees its RUNNING
            # job below instead of racing it into a second tenant.
            _lock_lead(lead)

            already_live = ProvisioningJob.objects.filter(
                lead=lead,
                status=ProvisioningJob.Status.SUCCESS,
                tenant__isnull=False,
            ).exists()
            if already_live:
                _log_provisioning_event("lead_provision_blocked", lead_id=lead.id, reason="already_provisioned")
                raise ValueError("Lead already provisioned. Use resend activation or package actions instead.")
            _block_or_supersede_running_jobs(lead)

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
            if is_reserved_slug(slug) or domain_name.lower() in _platform_hosts():
                _log_provisioning_event(
                    "lead_provision_blocked",
                    lead_id=lead.id,
                    reason="slug_reserved",
                    slug=slug,
                    domain=domain_name,
                )
                raise ValueError(f"'{slug}' is reserved by the platform and cannot be used as a restaurant address.")

            owner_email = lead.email or f"{slug}@example.com"
            user, created = User.objects.get_or_create(
                username=owner_email,
                defaults={
                    "email": owner_email,
                    "role": User.Roles.TENANT_OWNER,
                },
            )
            if created:
                # Temp password: user never sees it and authenticates via the
                # activation link, so it just needs to be strong and unguessable.
                # (User.objects.make_random_password() was removed in Django 5.1.)
                user.set_password(get_random_string(length=32))
            else:
                # Lock the existing account so two concurrent provisions can't both
                # adopt it, then refuse to silently move it off another restaurant.
                user = User.objects.select_for_update().get(pk=user.pk)
                _assert_owner_account_reusable(user, lead, owner_role=User.Roles.TENANT_OWNER)

            # Create the tenant ROW only. Physical-schema creation is deferred to
            # phase 2 (below), OUTSIDE this transaction — a new tenant's migrations
            # include AddIndexConcurrently (CREATE INDEX CONCURRENTLY), which Postgres
            # forbids inside a transaction. Building it in-transaction is the
            # MULTITENANCY-1 landmine that made every signup 500.
            tenant = Tenant(
                slug=slug,
                schema_name=slug,
                name=lead.name or slug,
                plan=plan,
            )
            tenant.auto_create_schema = False
            tenant.save()
            Domain.objects.create(domain=domain_name, tenant=tenant, is_primary=True)

            user.tenant = tenant
            user.save()

            Subscription.objects.get_or_create(tenant=tenant, plan=plan)

            job = ProvisioningJob.objects.create(
                lead=lead, tenant=tenant, status=ProvisioningJob.Status.RUNNING
            )
            job.append_log("Tenant, domain, owner and subscription created; building schema")

        # ── Phase 2: build the physical schema OUTSIDE the transaction ────────────
        # phase 1 has committed the public-schema rows; now run the tenant's
        # migrations (incl. the AddIndexConcurrently ones) with no transaction open.
        schema_name = tenant.schema_name
        # True once we know no schema of this name pre-dated this attempt — only then
        # is a leftover schema ours to drop on failure.
        schema_owned_by_attempt = False
        try:
            if schema_exists(schema_name):
                # Never adopt a pre-existing schema: create_schema(check_if_exists=True)
                # would return WITHOUT migrating it, and the tenant would go LIVE
                # half-migrated. (_availability already rejects such slugs; this is the
                # race backstop.)
                raise ValueError(
                    f"A database schema named '{schema_name}' already exists. "
                    "Retry provisioning to get a different address, or ask ops to remove the stray schema."
                )
            schema_owned_by_attempt = True
            tenant.create_schema(check_if_exists=True)
        except Exception as exc:
            logger.exception("Schema creation failed for tenant %s (lead %s)", slug, lead.id)
            _log_provisioning_event(
                "lead_provision_schema_failed",
                lead_id=lead.id,
                tenant_slug=slug,
                error=str(exc),
            )
            # Drop the partially-migrated schema THIS attempt created (auto_drop_schema
            # is off, so deleting the Tenant row below would orphan it); never touch a
            # schema that existed before we started.
            schema_dropped = schema_owned_by_attempt and _drop_schema_created_by_attempt(schema_name)
            with transaction.atomic():
                job.status = ProvisioningJob.Status.FAILED
                job.append_log(f"Schema creation failed: {exc}")
                if schema_owned_by_attempt:
                    job.append_log(
                        f"Partially-built schema '{schema_name}' dropped"
                        if schema_dropped
                        else f"WARNING: could not drop partially-built schema '{schema_name}'; "
                        "it blocks this slug until removed manually"
                    )
                job.save(update_fields=["status", "updated_at"])
                # Free the slug/domain so the lead can be retried: deleting the tenant
                # CASCADEs its Domain + Subscription and SET_NULLs this job + the owner.
                Tenant.objects.filter(pk=tenant.pk).delete()
            raise

        # ── Phase 3: schema exists — issue activation + finalize success ──────────
        # issue_activation SENDS the owner's activation email/WhatsApp, so it must run
        # only after the schema is real (a schema failure must not send a live link to
        # a tenant that no longer exists — this preserves the original ordering, where
        # activation ran after the in-transaction schema create).
        with transaction.atomic():
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

            job.append_log("Provisioning completed")
            _log_owner_links(
                job,
                token=activation.token,
                workspace_url=workspace_url,
                signin_url=signin_url,
                admin_url=admin_url,
                activation_url=activation_url,
                whatsapp_link=whatsapp_link,
            )
            job.status = ProvisioningJob.Status.SUCCESS
            job.save(update_fields=["status", "updated_at"])

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
    """Admin resend (platform console + Django admin action) — shared by both.

    Raises ``OwnerAlreadyActivatedError`` (a ``ValueError``) when the owner has
    already activated: since #457 the link would be rejected on click anyway.
    """
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            latest_job = _get_latest_provisioning_job(lead)
            tenant = latest_job.tenant
            user = _get_tenant_owner_user(tenant)
            _refuse_if_owner_activated(user, tenant)

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
            _log_owner_links(
                latest_job,
                token=activation.token,
                workspace_url=workspace_url,
                signin_url=signin_url,
                admin_url=admin_url,
                activation_url=activation_url,
                whatsapp_link=whatsapp_link,
            )
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


ACTIVATION_RESEND_PER_EMAIL_LIMIT = 3
ACTIVATION_RESEND_PER_EMAIL_WINDOW_SECONDS = 3600


def _activation_resend_cache_key(email: str) -> str:
    # Hash the normalized address: no raw email (PII) in cache keys, and case /
    # whitespace variants of the same mailbox share one counter.
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return f"activation_resend:{digest}"


def activation_resend_allowed(email: str) -> bool:
    """Per-email fixed-window cap on the PUBLIC activation resend (anti mail-flood).

    Complements the per-IP PublicLeadThrottle, which a distributed caller can
    rotate around. Counts every request for the address (known or not) so the
    limit itself reveals nothing. Same fixed-window add+incr pattern as the
    per-account login lockout; fails OPEN on a cache outage like that lockout.
    """
    key = _activation_resend_cache_key(email)
    try:
        cache.add(key, 0, ACTIVATION_RESEND_PER_EMAIL_WINDOW_SECONDS)
        count = cache.incr(key)
    except Exception:
        return True
    if count is None:  # django-redis IGNORE_EXCEPTIONS swallowed an outage
        return True
    return count <= ACTIVATION_RESEND_PER_EMAIL_LIMIT


def resend_activation_for_email(email: str) -> ActivationResendResult | None:
    """B1: self-service activation resend, keyed by the owner's email.

    Returns None (and sends nothing) when there is nothing to resend — the
    per-email resend quota is exhausted, unknown email, not an active tenant
    owner, or the account is ALREADY activated (``account_is_activated``: it has
    signed in before or enrolled MFA — account state, NOT token rows, which are
    pruned after 30 days). Callers (the public view) MUST return the same generic
    response regardless of the return value, to avoid account enumeration.
    """
    email = (email or "").strip()
    if not email:
        return None
    if not activation_resend_allowed(email):
        _log_provisioning_event("self_service_activation_resend_rate_limited")
        return None
    User = get_user_model()
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            # Activation is the OWNER onboarding flow: staff are invited with a
            # temp password (must_change_password) and never get a token, and a
            # deactivated account must not be handed a fresh credential.
            user = (
                User.objects.filter(
                    email__iexact=email,
                    tenant__isnull=False,
                    role=User.Roles.TENANT_OWNER,
                    is_active=True,
                )
                .select_related("tenant")
                .order_by("id")
                .first()
            )
            if user is None or user.tenant is None:
                return None
            tenant = user.tenant

            if account_is_activated(user):
                return None

            (
                activation,
                admin_url,
                workspace_url,
                signin_url,
                tenant_url,
                activation_url,
                whatsapp_link,
                whatsapp_message_template,
            ) = issue_activation(tenant, user, phone="")
            _log_provisioning_event(
                "self_service_activation_resent",
                tenant_id=getattr(tenant, "id", None),
                tenant_slug=getattr(tenant, "slug", ""),
                owner_user_id=getattr(user, "id", None),
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
    """Re-show the owner's onboarding package.

    The still-unused link is rebuilt from the ``ActivationToken`` row (never from the
    job log, which only ever holds the masked token); a new token is issued when
    there is none or ``refresh_token`` is set. Raises ``OwnerAlreadyActivatedError``
    when the owner has already activated (any activation link would be rejected).
    """
    with schema_context(get_public_schema_name()):
        with transaction.atomic():
            latest_job = _get_latest_provisioning_job(lead)
            tenant = latest_job.tenant
            user = _get_tenant_owner_user(tenant)
            _refuse_if_owner_activated(user, tenant)

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
            _log_owner_links(
                latest_job,
                token=token_obj.token,
                workspace_url=workspace_url,
                signin_url=signin_url,
                admin_url=admin_url,
                activation_url=activation_url,
                whatsapp_link=whatsapp_link,
            )
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
    invoice_amount=None,
    invoice_currency: str = "",
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
            # Persist invoice_amount so the owner can download a receipt without a manual
            # Django-admin edit. None leaves it unchanged (no amount provided yet).
            _save_fields = [
                "status",
                "admin_note",
                "payment_reference",
                "approved_by",
                "decided_at",
                "updated_at",
            ]
            if invoice_amount is not None:
                from decimal import Decimal as _Dec, InvalidOperation
                try:
                    upgrade_request.invoice_amount = _Dec(str(invoice_amount)).quantize(_Dec("0.01"))
                    _save_fields.append("invoice_amount")
                except (InvalidOperation, TypeError, ValueError):
                    pass  # ignore malformed amounts — do not crash the approval
            if invoice_currency:
                upgrade_request.invoice_currency = str(invoice_currency).strip().upper()[:8]
                _save_fields.append("invoice_currency")
            upgrade_request.save(update_fields=_save_fields)

            return TierUpgradeDecisionResult(
                upgrade_request=upgrade_request,
                tenant=tenant_obj,
                previous_plan=previous_plan,
                new_plan=target_plan,
            )
