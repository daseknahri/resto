# Kepoli Performance, SEO, and Hardening Checklist

Use this checklist before each production redeploy on Coolify.

## 1. Pre-Deploy (Local/Git)
- [ ] `git status` is clean.
- [ ] `npm run lint` passes in `frontend`.
- [ ] `npm run build` passes in `frontend`.
- [ ] `python manage.py check` passes in `backend`.
- [ ] Confirm latest commit hash/tag in release notes.

## 2. Deploy (Coolify)
- [ ] Trigger redeploy from `main`.
- [ ] Confirm all containers are healthy (`frontend`, `admin`, `api`, `postgres`, `redis`).
- [ ] Verify no repeated restarts in Coolify logs.

## 3. Post-Deploy Health
- [ ] `https://menu.kepoli.com/health` returns `200`.
- [ ] `https://admin.menu.kepoli.com/health` returns `200`.
- [ ] `https://api.kepoli.com/api/health/` returns `200`.
- [ ] Tenant wildcard path works: `https://<tenant>.menu.kepoli.com/menu`.

## 4. SEO Validation (Customer Host)
- [ ] View source/DevTools shows:
  - [ ] `<title>` contains tenant name + page label.
  - [ ] `meta[name="description"]` is present and tenant-aware.
  - [ ] `link[rel="canonical"]` is present.
  - [ ] OpenGraph tags (`og:title`, `og:description`, `og:url`) are present.
  - [ ] Twitter tags are present.
- [ ] JSON-LD exists on customer pages: `script#tenant-restaurant-jsonld`.
- [ ] Admin/owner/auth pages are `noindex,nofollow`.

## 5. Mobile Performance Validation
- [ ] Menu page scrolls smoothly with many categories.
- [ ] Last category card is fully visible above sticky bottom cart/nav.
- [ ] Hero image is visible quickly (no long blank flash).
- [ ] Language dropdown opens above content (no clipping/overlap).
- [ ] Category and dish cards render without layout jumps.

## 6. Core Business Flow Smoke
- [ ] Lead submitted from landing.
- [ ] Admin can provision lead successfully.
- [ ] Activation link works.
- [ ] Owner can publish menu.
- [ ] Customer can browse categories/dishes.
- [ ] Cart WhatsApp handoff works.

## 7. Rollback Readiness
- [ ] Latest DB backup exists in `/var/backups/kepoli`.
- [ ] Restore dry run command validated.
- [ ] Previous known-good deploy hash is documented.
