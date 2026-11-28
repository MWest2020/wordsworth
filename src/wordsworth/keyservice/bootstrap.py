"""``wordsworth-keyservice-init``: create the service's schema and nothing
else -- no admin role (roles arrive with ``key-service-reveal``). Refuses
first (design.md "Refuse to start"), the same check ``serve.py`` runs on
startup."""
from __future__ import annotations

from .config import settings
from .db import (check_openbao_refuse_to_start,
                 check_pseudonymise_cap_refuse_to_start,
                 check_refuse_to_start, init_schema, make_engine)


def main() -> int:
    check_refuse_to_start(settings.database_url)
    check_openbao_refuse_to_start(settings.openbao_url, settings.openbao_token)
    check_pseudonymise_cap_refuse_to_start(settings.pseudonymise_max_items)
    engine = make_engine()
    init_schema(engine)
    print("key-service schema ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
