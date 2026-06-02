"""Channel-group naming. Kept pure (no Channels import) so the tenant-isolation
guarantee is unit-tested in isolation."""


def tenant_group(schema_name, channel):
    """Build a Channels group name scoped to one tenant schema.

    The schema name is the isolation boundary: a broadcast to ``t.<schema>.owner``
    can only reach sockets that joined the *same* tenant's group, so one
    restaurant's events never leak to another. Inputs are sanitised to the
    characters Channels allows in group names (ASCII alphanumerics, ``-`` ``_``
    ``.``) and capped under the 100-char limit.
    """
    safe_schema = "".join(c for c in str(schema_name or "") if c.isalnum() or c in "_-") or "public"
    safe_channel = "".join(c for c in str(channel or "") if c.isalnum() or c in "_-") or "events"
    return f"t.{safe_schema}.{safe_channel}"[:90]
