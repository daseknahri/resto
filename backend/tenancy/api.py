import io
import json
import os
import posixpath
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from urllib.parse import unquote, urlparse

from django.conf import settings
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
from tenancy.models import Profile
from tenancy.serializers import ProfileSerializer, TenantMetaSerializer

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageOps = None
    UnidentifiedImageError = Exception

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_SIZE = (1800, 1800)
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
    if user.is_superuser or user.is_staff or user.is_platform_admin:
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
        return (
            raw,
            _safe_extension(uploaded_file.name),
            uploaded_file.content_type or "application/octet-stream",
            normalized_variant,
        )


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


@method_decorator(ensure_csrf_cookie, name="dispatch")
class TenantMetaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved"}, status=400)
        serializer = TenantMetaSerializer.from_tenant(tenant, request=request)
        return Response(serializer.data)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        tenant = getattr(self.request, "tenant", None)
        profile, _ = Profile.objects.get_or_create(tenant=tenant)
        return profile


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
        if not (upload.content_type or "").startswith("image/"):
            return Response({"image": ["Only image uploads are allowed."]}, status=400)

        variant = (request.data.get("variant") or "").strip().lower()
        if variant and variant not in VARIANT_SPECS:
            return Response({"variant": ["Unsupported image variant."]}, status=400)

        data, ext, content_type, normalized_variant = _optimize_image(upload, variant=variant)
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
            body = exc.read().decode("utf-8", errors="replace")[:200]
            return Response(
                {"detail": f"Translation provider error ({exc.code}).", "code": "provider_error", "body": body},
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
