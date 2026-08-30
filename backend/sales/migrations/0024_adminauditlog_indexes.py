from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Index AdminAuditLog by created_at (and tenant + created_at).

    AdminAuditLog is an unbounded, append-only public-schema audit table. It had
    ZERO indexes, so:
      * the admin audit-log list (default sort ``-created_at`` + COUNT + slice)
        did a full sequential scan + unindexed sort on every page view;
      * the per-tenant admin timeline
        (``filter(tenant_id=...).order_by("-created_at")``) did the same;
      * the prune job (``prune_admin_audit_logs`` -> ``filter(created_at__lt=cutoff)``
        + COUNT + DELETE) full-scanned to find the rows to delete.

    ``adminauditlog_created_idx`` (-created_at) serves the default list sort/count
    and the prune range scan; ``adminaudit_tenant_created_idx`` (tenant, -created_at)
    serves the per-tenant timeline. No ``action`` index: the ``action`` exact-match
    filter is optional/secondary (the default page load is unfiltered) and the
    admin ``q`` search uses ``icontains`` on ``action`` (not btree-serviceable), so
    an index there would only add write overhead on a hot append-only table.

    atomic=False + AddIndexConcurrently: CREATE INDEX CONCURRENTLY builds the index
    without an ACCESS EXCLUSIVE lock (per backend/MIGRATIONS.md), so the migration
    does not block writes to this live, high-write table on deploy.
    """

    atomic = False

    dependencies = [
        ('sales', '0023_field_option_hygiene'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='adminauditlog',
            index=models.Index(fields=['-created_at'], name='adminauditlog_created_idx'),
        ),
        AddIndexConcurrently(
            model_name='adminauditlog',
            index=models.Index(fields=['tenant', '-created_at'], name='adminaudit_tenant_created_idx'),
        ),
    ]
