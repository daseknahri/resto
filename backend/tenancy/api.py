import io
import json
import logging
import os
import posixpath
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.throttles import TranslateThrottle
from tenancy.cache_utils import get_or_build_single_flight
from tenancy.models import Profile
from tenancy.serializers import ProfileSerializer, TenantMetaSerializer

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageOps = None
    UnidentifiedImageError = Exception

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_SIZE = (1800, 1800)

# Content-types that are image/* but can contain active script content and must
# be blocked regardless of what the client claims.
_BLOCKED_IMAGE_CONTENT_TYPES = frozenset({
    "image/svg+xml",
    "image/svg",
    "image/x-icon",   # ICO can embed PE executables
    "image/vnd.microsoft.icon",
})
VARIANT_SPECS = {
    "logo": {"aspect_ratio": 1.0, "max_size": (900, 900)},
    "hero": {"aspect_ratio": 16 / 9, "max_size": (1800, 1012)},
    "category": {"aspect_ratio": 4 / 3, "max_size": (1400, 1050)},
    "dish": {"aspect_ratio": 4 / 3, "max_size": (1400, 1050)},
}


def _can_edit_tenant(request) -> bool:
    user = request.user
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    # OPS-5b: is_staff (Django /admin/ flag) dropped — it granted cross-tenant
    # profile/settings write to any Django staff user. Real admins have is_superuser.
    if user.is_superuser or user.is_platform_admin:
        return True
    if tenant is None or user.tenant_id != tenant.id:
        return False
    return user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}


def _safe_extension(upload_name: str) -> str:
    ext = os.path.splitext(upload_name or "")[1].lower().strip(".")
    return ext if ext in {"jpg", "jpeg", "png", "webp"} else "jpg"


def _center_crop_to_ratio(image, ratio: float):
    width, height = image.size
    if width <= 0 or height <= 0 or not ratio:
        return image

    current_ratio = width / height
    if abs(current_ratio - ratio) <= 0.01:
        return image

    if current_ratio > ratio:
        new_width = int(height * ratio)
        left = max((width - new_width) // 2, 0)
        return image.crop((left, 0, left + new_width, height))

    new_height = int(width / ratio)
    top = max((height - new_height) // 2, 0)
    return image.crop((0, top, width, top + new_height))


def _optimize_image(uploaded_file, variant: str = ""):
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    normalized_variant = (variant or "").strip().lower()
    spec = VARIANT_SPECS.get(normalized_variant, {})

    if Image is None:
        return (
            raw,
            _safe_extension(uploaded_file.name),
            uploaded_file.content_type or "application/octet-stream",
            normalized_variant,
        )

    try:
        image = Image.open(io.BytesIO(raw))
        if ImageOps is not None:
            image = ImageOps.exif_transpose(image)

        ratio = spec.get("aspect_ratio")
        if ratio:
            image = _center_crop_to_ratio(image, ratio)

        max_size = spec.get("max_size", DEFAULT_MAX_SIZE)
        image.thumbnail(max_size)

        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background

        out = io.BytesIO()
        image.save(out, format="WEBP", quality=84, method=6)
        return out.getvalue(), "webp", "image/webp", normalized_variant
    except (UnidentifiedImageError, OSError, ValueError):
        # OPS-5c item 1: Pillow could not decode the bytes — the file is not a
        # valid image (could be a JPEG/SVG polyglot or corrupt upload).  Do NOT
        # echo the client-supplied content_type; instead raise so the caller can
        # reject the upload.  Trusting the client type on a transcode failure
        # would let a polyglot be stored and served with a trusted MIME type.
        raise


def _tenant_upload_prefix(tenant_slug: str) -> str:
    slug = (tenant_slug or "public").strip().lower() or "public"
    return f"uploads/{slug}/"


def _extract_relative_media_path(value: str) -> str:
    """Extract safe storage-relative media path from URL/path input."""
    raw = (value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    media_prefix = (settings.MEDIA_URL or "/media/").strip() or "/media/"
    if not media_prefix.startswith("/"):
        media_prefix = f"/{media_prefix}"

    if parsed.scheme or parsed.netloc:
        path = parsed.path or ""
        if not path.startswith(media_prefix):
            return ""
        candidate = path[len(media_prefix) :]
    else:
        if raw.startswith("/"):
            if raw.startswith(media_prefix):
                candidate = raw[len(media_prefix) :]
            else:
                return ""
        else:
            candidate = raw

    candidate = unquote(candidate).lstrip("/")
    candidate = posixpath.normpath(candidate)

    if candidate in {"", ".", ".."}:
        return ""
    if candidate.startswith("../") or candidate.startswith("/"):
        return ""
    return candidate


# ── Meta cache constants ────────────────────────────────────────────────────────
# Cache key pattern: meta:v1:{tenant_slug}:{locale_key}
# locale_key = "_auth"   → authenticated owner (canonical, unlocalized fields)
#            = "en"/"fr"/"ar" → customer with explicit ?lang= param
#            = ""             → unauthenticated customer with no ?lang= param
# On profile save every known variant is evicted so the cache is never stale.
_META_CACHE_TTL = 300        # 5 minutes — matches the frontend SWR TTL
_META_CACHE_LOCK_TTL = 10   # seconds; lock auto-expires if a holder dies mid-build
_META_CACHE_WAIT_TOTAL = 2.0  # seconds; max a follower waits for the holder's value
_META_CACHE_WAIT_STEP = 0.05  # seconds; poll interval while waiting
_META_CACHE_LOCALE_VARIANTS = ("", "en", "fr", "ar", "_auth")


def _meta_cache_key(tenant_slug: str, locale_key: str) -> str:
    return f"meta:v1:{tenant_slug}:{locale_key}"


def _bust_tenant_meta_cache(tenant_slug: str) -> None:
    """Delete every known locale variant of the meta cache for this tenant."""
    if not tenant_slug:
        return
    keys = [_meta_cache_key(tenant_slug, loc) for loc in _META_CACHE_LOCALE_VARIANTS]
    cache.delete_many(keys)


# ── Live (time-sensitive) is_open_now recompute for the cached meta payload ──────
# The /api/meta/ response is cached whole (the EXPENSIVE TenantMetaSerializer work),
# busted only on a Profile save — never on time passage. But profile.is_open_now is a
# TIME-SENSITIVE verdict (it evaluates the weekly schedule in tenant-local time), so a
# warm cache froze the open/closed verdict for up to the TTL and could disagree with the
# now-live marketplace listing card (accounts.views._refresh_marketplace_live_fields,
# used as the template here). Fix: the cached payload also carries the RAW INPUTS the
# verdict derives from (under the internal "_isopen_raw" key), and this pass recomputes
# is_open_now from CURRENT time on EVERY request — cache hit and fresh build alike — then
# strips the internal key from the COPY returned to the client. The cached object keeps
# its raw inputs so a later hit can recompute too. No DB access here: the schedule
# recompute is pure in-memory, and closure_today is cached (day-stable). The only edge —
# a ClosureDate that begins/ends across midnight — is at most TTL (5 min) stale, accepted.
_META_ISOPEN_RAW_KEY = "_isopen_raw"


def _refresh_meta_is_open_now(payload):
    """Return a response COPY of *payload* with profile.is_open_now recomputed NOW.

    Overwrites payload["profile"]["is_open_now"] from the cached raw inputs under
    payload["_isopen_raw"] + the current time, reusing the SINGLE-source helpers
    (openstate.schedule_open_now + a tenant-local now built from the raw timezone via
    the same chain as openstate.tenant_local_now) — NO forked rule. The recompute mirrors
    ProfileSerializer.get_is_open_now's guard order EXACTLY: manual is_open off → False;
    menu temporarily disabled → False; today is a closure date → False; else delegate to
    the window rule, falling back to the manual is_open when no schedule is configured
    (result is None). Verdict is IDENTICAL to get_is_open_now at the same instant — this
    is a freshness fix, not a logic change.

    Operates on a deepcopy so the cached object keeps "_isopen_raw" intact for the next
    hit. Then strips "_isopen_raw" from the copy so it never leaks to the client. Pure
    in-memory — no DB access (closure_today is a cached day-stable bool).
    """
    import copy
    from datetime import datetime as _dt, timezone as _utc

    out = copy.deepcopy(payload) if payload else payload
    if not isinstance(out, dict):
        return out

    raw = out.pop(_META_ISOPEN_RAW_KEY, None)
    profile = out.get("profile")
    if isinstance(raw, dict) and isinstance(profile, dict) and "is_open_now" in profile:
        if not raw.get("is_open"):
            verdict = False
        elif raw.get("menu_disabled"):
            verdict = False
        elif raw.get("closure_today"):
            verdict = False
        else:
            # Build a tenant-local now from the raw timezone via the SAME chain as
            # openstate.tenant_local_now (timezone → settings.TIME_ZONE → UTC, safe UTC
            # fallback on any error), then delegate to the SINGLE window rule.
            from .openstate import schedule_open_now
            try:
                from zoneinfo import ZoneInfo
                tz_name = (raw.get("timezone") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
                now_local = _dt.now(ZoneInfo(tz_name))
            except Exception:
                now_local = _dt.now(_utc.utc)
            result = schedule_open_now(raw.get("schedule"), now_local)
            verdict = bool(raw.get("is_open")) if result is None else result
        profile["is_open_now"] = bool(verdict)

    return out


@method_decorator(ensure_csrf_cookie, name="dispatch")
class TenantMetaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved"}, status=400)

        tenant_slug = getattr(tenant, "slug", "")

        # Determine locale scope for the cache key.
        # Authenticated users (owners) always get canonical (unlocalized) data.
        # Anonymous customers use the ?lang= query param; Accept-Language header
        # requests fall under the same "" bucket (the minority path).
        user = getattr(request, "user", None)
        is_auth = user is not None and getattr(user, "is_authenticated", False)
        if is_auth:
            locale_key = "_auth"
        else:
            query_params = getattr(request, "query_params", None) or getattr(request, "GET", {})
            lang_param = str(query_params.get("lang", "") or "").strip().lower()[:8]
            locale_key = lang_param  # "" when no ?lang= is given

        cache_key = _meta_cache_key(tenant_slug, locale_key)

        def _build():
            # The expensive TenantMetaSerializer rebuild — runs at most once per key under
            # concurrency (single-flight via get_or_build_single_flight). Returns the
            # payload WITH the internal "_isopen_raw" inputs; the post-cache live recompute
            # (_refresh_meta_is_open_now) strips them before the HTTP response.
            serializer = TenantMetaSerializer.from_tenant(tenant, request=request)
            built_data = serializer.data
            # Attach the RAW INPUTS needed to recompute is_open_now on later cache hits
            # with NO DB query: the manual is_open + temp-disable toggles, the weekly
            # schedule, the timezone, and whether TODAY is a closure date (computed ONCE
            # here with the same ClosureDate query the serializer uses, so the cache-hit
            # path needs no DB). These live under the internal "_isopen_raw" key and are
            # stripped from the HTTP response by _refresh_meta_is_open_now.
            profile = getattr(tenant, "profile", None)
            if profile is not None and isinstance(built_data.get("profile"), dict):
                try:
                    from menu.models import ClosureDate
                    from django.utils import timezone as _tz
                    closure_today = ClosureDate.objects.filter(date=_tz.localdate()).exists()
                except Exception:
                    closure_today = False
                built_data[_META_ISOPEN_RAW_KEY] = {
                    "is_open": bool(getattr(profile, "is_open", True)),
                    "menu_disabled": bool(getattr(profile, "is_menu_temporarily_disabled", False)),
                    "schedule": getattr(profile, "business_hours_schedule", None),
                    "timezone": getattr(profile, "timezone", "") or "",
                    "closure_today": bool(closure_today),
                }
            # Pickle-safe: DRF ReturnDict/ReturnList are picklable by django-redis. The
            # single-flight helper will cache.set() this payload WITH _isopen_raw so every
            # subsequent cache hit can recompute is_open_now without a DB round-trip.
            return built_data

        # Single-flight: on a cache miss at peak, only one request runs _build(); the rest
        # wait briefly then read the freshly populated value. Mirrors the MarketplaceView /
        # DirectoryView pattern exactly (accounts.views._public_list_get_or_build).
        payload = get_or_build_single_flight(
            cache_key,
            _build,
            ttl=_META_CACHE_TTL,
            lock_ttl=_META_CACHE_LOCK_TTL,
            wait_total=_META_CACHE_WAIT_TOTAL,
            wait_step=_META_CACHE_WAIT_STEP,
        )
        # Recompute the time-sensitive open/closed verdict (profile.is_open_now) live at
        # request time off the cached raw inputs (no DB), strip the internal key, and
        # return the fresh copy. This runs on EVERY request — cache hit, fresh build, and
        # lock-wait follower alike — so the open/closed state is never frozen for a TTL.
        return Response(_refresh_meta_is_open_now(payload))


# Profile fields the PUBLIC marketplace + directory listings depend on. Editing any
# of these changes what the cross-tenant listing shows (membership, a result's
# serialized fields, the open/closed verdict, or a facet list), so a save touching one
# must bust the GLOBAL public-list cache (accounts.views._bust_public_list_cache).
# Derived from the two views in accounts/views.py:
#   DirectoryView   — directory_opt_in/is_menu_published/tenant active (membership);
#                     city, cuisine_type (filter + facet); tagline, logo_url,
#                     business_type, delivery_enabled (serialized); is_open via
#                     _compute_is_open_now (is_open / is_menu_temporarily_disabled /
#                     business_hours_schedule / timezone).
#   MarketplaceView — + delivery_enabled, price_tier (filter); tags (filter + facet);
#                     address, delivery_fee, delivery_minimum_order, lat, lng,
#                     business_hours_schedule (serialized); timezone (open + promo tz).
# Excluded on purpose: rating_avg/rating_count + marketplace_promos (own denorm bust
# paths) and unrelated config (notify_*/winback_*/commission/…).
LISTING_RELEVANT_FIELDS = frozenset({
    "directory_opt_in",
    "is_menu_published",
    "is_open",
    "is_menu_temporarily_disabled",
    "business_hours_schedule",
    "timezone",
    "city",
    "cuisine_type",
    "delivery_enabled",
    "delivery_fee",
    "delivery_minimum_order",
    "price_tier",
    "tags",
    "business_type",
    "logo_url",
    "tagline",
    "address",
    "lat",
    "lng",
})


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        tenant = getattr(self.request, "tenant", None)
        profile, _ = Profile.objects.get_or_create(tenant=tenant)
        return profile

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Evict every cached locale variant so the next /api/meta/ read is fresh.
        tenant = getattr(self.request, "tenant", None)
        _bust_tenant_meta_cache(getattr(tenant, "slug", ""))
        # If the save touched a field the PUBLIC marketplace/directory listing depends
        # on (e.g. directory_opt_in OFF, city, hours…), also bust the global public-list
        # cache so the listing reflects it immediately instead of waiting out the 90s
        # TTL. Skip when only unrelated settings changed (do not invalidate everyone's
        # listing on an unrelated save). Lazy import avoids a tenancy->accounts cycle.
        if set(getattr(serializer, "validated_data", None) or {}) & LISTING_RELEVANT_FIELDS:
            try:
                from accounts.views import _bust_public_list_cache
                _bust_public_list_cache()
            except Exception:
                pass


class ImageUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant(request):
            return Response({"detail": "Menu editor access required."}, status=403)

        upload = request.FILES.get("image")
        if upload is None:
            return Response({"image": ["Image file is required."]}, status=400)
        if upload.size > MAX_UPLOAD_BYTES:
            return Response({"image": ["Image too large. Max size is 8MB."]}, status=400)
        ct = (upload.content_type or "").strip().lower()
        if not ct.startswith("image/"):
            return Response({"image": ["Only image uploads are allowed."]}, status=400)
        if ct in _BLOCKED_IMAGE_CONTENT_TYPES:
            return Response({"image": ["SVG and icon uploads are not permitted."]}, status=400)

        variant = (request.data.get("variant") or "").strip().lower()
        if variant and variant not in VARIANT_SPECS:
            return Response({"variant": ["Unsupported image variant."]}, status=400)

        try:
            data, ext, content_type, normalized_variant = _optimize_image(upload, variant=variant)
        except (UnidentifiedImageError, OSError, ValueError):
            # OPS-5c item 1: Pillow could not decode the image — reject instead of
            # echoing the client-supplied content_type (polyglot-upload guard).
            return Response({"image": ["Could not decode image. Upload a valid JPEG, PNG, WEBP, or GIF."]}, status=400)
        tenant = getattr(request, "tenant", None)
        tenant_slug = getattr(tenant, "slug", "public")
        now = datetime.utcnow()
        rel_path = f"uploads/{tenant_slug}/{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"
        saved = default_storage.save(rel_path, ContentFile(data))
        url = default_storage.url(saved)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        return Response({"url": url, "path": saved, "content_type": content_type, "variant": normalized_variant}, status=201)


_TRANSLATE_LANG_NAMES = {"en": "English", "fr": "French", "ar": "Arabic"}
_TRANSLATE_SUPPORTED = set(_TRANSLATE_LANG_NAMES.keys())


class TranslateView(APIView):
    """
    POST /api/translate/
    Body: { text, target_lang, source_lang? }
    Returns: { translated, source_lang, target_lang }
    Requires OPENROUTER_API_KEY in environment.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [TranslateThrottle]  # 30 calls/hour per user — prevents credit drain
    MAX_TEXT_LEN = 2000

    def _call_openrouter(self, text: str, target_lang: str, source_lang: str) -> str:
        from django.conf import settings as _settings

        api_key = getattr(_settings, "OPENROUTER_API_KEY", "").strip()
        model = getattr(_settings, "OPENROUTER_MODEL", "google/gemma-3-12b-it:free").strip()
        site_url = getattr(_settings, "PUBLIC_MENU_BASE_URL", "").strip() or "https://restomenu.app"

        target_name = _TRANSLATE_LANG_NAMES.get(target_lang, target_lang)
        if source_lang and source_lang != "auto" and source_lang in _TRANSLATE_LANG_NAMES:
            source_hint = f" from {_TRANSLATE_LANG_NAMES[source_lang]}"
        else:
            source_hint = ""

        prompt = (
            f"Translate the following text{source_hint} to {target_name}. "
            "Return ONLY the translated text, no explanation, no quotes, no labels:\n\n"
            f"{text}"
        )

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": site_url,
                "X-Title": "Restomenu",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return data["choices"][0]["message"]["content"].strip()

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant(request):
            return Response({"detail": "Menu editor access required."}, status=403)

        from django.conf import settings as _settings
        if not getattr(_settings, "OPENROUTER_API_KEY", "").strip():
            return Response(
                {"detail": "Translation service not configured.", "code": "not_configured"},
                status=503,
            )

        text = str(request.data.get("text") or "").strip()
        target_lang = str(request.data.get("target_lang") or "").strip().lower()
        source_lang = str(request.data.get("source_lang") or "auto").strip().lower()

        if not text:
            return Response({"text": ["This field is required."]}, status=400)
        if len(text) > self.MAX_TEXT_LEN:
            return Response({"text": [f"Must be {self.MAX_TEXT_LEN} characters or fewer."]}, status=400)
        if target_lang not in _TRANSLATE_SUPPORTED:
            return Response(
                {"target_lang": [f"Must be one of: {', '.join(sorted(_TRANSLATE_SUPPORTED))}."]},
                status=400,
            )

        try:
            translated = self._call_openrouter(text, target_lang, source_lang)
        except urllib.error.HTTPError as exc:
            # Log the upstream body server-side only; never echo a third-party provider's
            # raw error body to the client (it can leak provider internals / keys / quota
            # detail). Return a generic message instead.
            body = exc.read().decode("utf-8", errors="replace")[:500]
            logger.warning("Translation provider HTTPError %s: %s", exc.code, body)
            return Response(
                {"detail": "Translation provider error.", "code": "provider_error"},
                status=502,
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            return Response(
                {"detail": "Translation service unreachable.", "code": "provider_unavailable"},
                status=502,
            )
        except (KeyError, IndexError, json.JSONDecodeError):
            return Response(
                {"detail": "Unexpected response from translation service.", "code": "provider_error"},
                status=502,
            )

        return Response(
            {"translated": translated, "source_lang": source_lang, "target_lang": target_lang},
            status=200,
        )


class ImageDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant(request):
            return Response({"detail": "Menu editor access required."}, status=403)

        value = request.data.get("value") or request.data.get("url") or request.data.get("path")
        rel_path = _extract_relative_media_path(value)
        if not rel_path:
            return Response({"detail": "Valid image path/url is required."}, status=400)

        tenant = getattr(request, "tenant", None)
        tenant_slug = getattr(tenant, "slug", "public")
        if not rel_path.startswith(_tenant_upload_prefix(tenant_slug)):
            return Response({"detail": "Cannot delete files outside your tenant uploads."}, status=403)

        existed = default_storage.exists(rel_path)
        if existed:
            default_storage.delete(rel_path)

        return Response({"deleted": bool(existed), "path": rel_path}, status=200)


class OwnerDeletionRequestView(APIView):
    """
    POST /api/owner/deletion-request/

    Owner requests account deletion.  Sets `deletion_requested_at` on the
    Tenant record (public schema) and sends an admin notification email.
    The actual deactivation is carried out manually by an admin.

    Body (optional):
        { "reason": "Closing my business" }

    Responses:
        200 OK  — request recorded (idempotent — calling twice is safe)
        403     — non-owner access
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        tenant = getattr(request, "tenant", None)

        # Only the restaurant owner may request deletion.
        if not getattr(user, "is_tenant_owner", False):
            return Response({"detail": "Owner access required."}, status=403)

        if tenant is None:
            return Response({"detail": "No tenant context."}, status=400)

        reason = str(request.data.get("reason", "") or "").strip()[:500]

        from django.utils import timezone as _tz
        from django_tenants.utils import schema_context

        # Write to public schema (Tenant lives there).
        with schema_context("public"):
            from tenancy.models import Tenant as _Tenant
            try:
                t = _Tenant.objects.get(pk=tenant.pk)
            except _Tenant.DoesNotExist:
                return Response({"detail": "Tenant not found."}, status=404)

            # Idempotent — only set if not already requested.
            if not t.deletion_requested_at:
                t.deletion_requested_at = _tz.now()
            t.deletion_reason = reason
            t.save(update_fields=["deletion_requested_at", "deletion_reason"])

        # Notify admin via email (best-effort — never fail the response).
        try:
            from django.conf import settings as _s
            from django.core.mail import send_mail as _send
            admin_email = getattr(_s, "DEFAULT_FROM_EMAIL", "")
            if admin_email:
                _send(
                    subject=f"[Resto] Deletion request — {tenant.slug}",
                    message=(
                        f"Restaurant '{tenant.name}' (slug: {tenant.slug}) has requested account deletion.\n\n"
                        f"Owner: {user.email}\n"
                        f"Reason: {reason or '(none provided)'}\n\n"
                        "Please review in the admin console and complete the offboarding process."
                    ),
                    from_email=admin_email,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
        except Exception:
            pass

        # OPS-5b: audit the deletion request in AdminAuditLog for GDPR compliance timeline.
        try:
            from sales.audit import log_admin_action
            from sales.models import AdminAuditLog
            log_admin_action(
                action=AdminAuditLog.Actions.TENANT_DELETION_REQUESTED,
                request=request,
                tenant=t,
                target_repr=f"tenant:{t.slug}",
                metadata={
                    "tenant_id": t.id,
                    "tenant_slug": t.slug,
                    "requested_at": t.deletion_requested_at.isoformat(),
                    "reason": reason or "",
                },
            )
        except Exception:
            pass  # Never fail the response due to audit logging

        return Response({"status": "requested", "deletion_requested_at": t.deletion_requested_at.isoformat()})


class AppManifestView(APIView):
    """
    GET /app-manifest.json
    Returns a W3C Web App Manifest for the current tenant, used by the customer-
    facing PWA so the installed app shows the restaurant's own name and colours.
    Served with the correct Content-Type so browsers recognise it as a manifest.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return JsonResponse({"error": "tenant not found"}, status=400)

        # Pull profile fields
        profile = getattr(tenant, "profile", None)
        restaurant_name = getattr(tenant, "name", "Restaurant") or "Restaurant"
        short_name = restaurant_name[:12]  # manifest short_name limit
        logo_url = (getattr(profile, "logo_url", "") or "").strip()
        primary_color = (getattr(profile, "primary_color", "") or "#0b1c1a").strip() or "#0b1c1a"
        secondary_color = (getattr(profile, "secondary_color", "") or "#F59E0B").strip() or "#F59E0B"

        # "any" and "maskable" are kept as separate entries: reusing one edge-to-edge
        # icon for the maskable purpose lets the launcher crop the artwork.  The
        # /icon-maskable-* assets carry safe-zone padding so they survive any mask.
        icons = [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
        ]
        if logo_url:
            icons.insert(0, {"src": logo_url, "sizes": "any", "type": "image/png", "purpose": "any"})

        manifest = {
            "name": restaurant_name,
            "short_name": short_name,
            "description": f"Order online from {restaurant_name}",
            "start_url": "/browse",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": primary_color,
            "theme_color": secondary_color,
            "icons": icons,
            "categories": ["food"],
        }

        response = JsonResponse(manifest)
        response["Content-Type"] = "application/manifest+json"
        response["Cache-Control"] = "public, max-age=3600"
        return response
