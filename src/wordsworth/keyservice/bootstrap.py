"""``wordsworth-keyservice-init``: create the service's schema and ensure
the admin role (design.md "Identity", mirrors
``wordsworth.bootstrap.ensure_admin_role``). Refuses first (design.md
"Refuse to start"), the same check ``serve.py`` runs on startup."""
from __future__ import annotations

from . import roles
from .config import settings
from .db import (check_openbao_refuse_to_start,
                 check_pseudonymise_cap_refuse_to_start,
                 check_refuse_to_start, init_schema, make_engine,
                 make_session_factory)


def main() -> int:
    check_refuse_to_start(settings.database_url)
    check_openbao_refuse_to_start(settings.openbao_url, settings.openbao_token)
    check_pseudonymise_cap_refuse_to_start(settings.pseudonymise_max_items)
    engine = make_engine()
    init_schema(engine)
    print("key-service schema ready")
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        print(roles.ensure_admin_role(session, actor="installation"))
        session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
