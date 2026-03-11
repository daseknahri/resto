# I18N Content Model Strategy

## Goal
Enable multilingual menu content per tenant without breaking existing onboarding and production data.

## Implemented Foundation
- Added translation JSON fields:
  - `Category.name_i18n`, `Category.description_i18n`
  - `Dish.name_i18n`, `Dish.description_i18n`
  - `DishOption.name_i18n`
- Added locale-aware serializer fallback for public menu reads:
  - Locale source priority: `?lang=` query param, then `Accept-Language`
  - Fallback: base field (`name` / `description`), then first non-empty translation
- Added plan-aware validation:
  - Number of translation entries is capped by tenant plan `max_languages`
- Added export/import compatibility:
  - Tenant settings export now includes `*_i18n` maps
  - Tenant settings import restores `*_i18n` maps

## Safety Rule
- Authenticated owner/admin contexts return canonical base fields by default.
- Locale substitution is applied for public/anonymous menu responses, to avoid overwriting base values during owner editing.

## Frontend Runtime Behavior
- API clients now send locale context on read requests:
  - `Accept-Language: <active-locale>`
  - `lang=<active-locale>` query param (if not already provided)

## Migration
- Migration file: `backend/menu/migrations/0004_menu_i18n_fields.py`

## Next Step (UI)
- Extend owner wizard forms to edit translations explicitly:
  - `name_i18n` and `description_i18n`
  - Plan-aware UX (show allowed language count, disable extra locales)
  - Keep base language clearly labeled to prevent accidental overwrite

## UI Progress (Completed)
- Category wizard now supports:
  - Base description field
  - Translated category name/description inputs per selected locale
  - Locale selection constrained by plan language limit
- Dish wizard now supports:
  - Translated dish name/description inputs per selected locale
  - Translated variant/option name inputs per selected locale
  - Locale selection constrained by plan language limit
- Locale selections now hydrate from existing saved translation maps, so previously saved locales are preserved in the editor UI.
- Shared runtime error fallbacks are localized as well:
  - Session store auth fallback messages
  - API client 429/rate-limit fallback detail
- Coverage audit completed for UI layers:
  - `frontend/src/pages`
  - `frontend/src/layouts`
  - `frontend/src/components`
  - `frontend/src/onboarding`
