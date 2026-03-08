from django.db import models

from tenancy.models import Tenant


class Profile(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="profile")
    tagline = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    google_maps_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#0F766E")
    secondary_color = models.CharField(max_length=7, default="#F59E0B")
    language = models.CharField(max_length=5, default="en")
    logo_url = models.URLField(blank=True)
    hero_url = models.URLField(blank=True)

    def __str__(self):
        return f"Profile for {self.tenant.slug}"
