# SUPER_ADMIN rollout

1. Deploy the application changes and run `create_super_admin_role.sql` against
   the application database. It creates a role only and promotes nobody.
2. Have the database operator assign the first SUPER_ADMIN to an explicitly
   approved, active user. Use their numeric `users.id`, not employee code.
   Record the assignment in `audit_log`, increment that user's `session_version`,
   and invalidate RBAC caches. No default username is selected by this change.
3. Sign in again. The effective session/permission roles include ADMIN for
   SUPER_ADMIN, while database role assignments remain unchanged.
4. Subsequent promotions are available to SUPER_ADMIN in Settings. ADMIN keeps
   ordinary user and role management but cannot mutate SUPER_ADMIN users,
   memberships, role permissions, or role menus. The protected system role cannot
   be renamed/deleted. Removing the last active SUPER_ADMIN is rejected.

Existing report ADMIN checks and user-selected filters are retained. SUPER_ADMIN
bypasses automatic franchise restrictions even with FRANCHISE_INDIA_HEAD assigned.
Permission entries named ADMIN/SUPER_ADMIN are not a substitute for actual roles.

Run isolated tests (no live database or Redis):

```sh
PYTHONPATH=server venv/bin/python -m unittest discover -s server/tests -p test_super_admin.py
```

Before production rollout, verify browser login, role changes, relevant report
exports and filter caches with representative users. The automated SQLite tests
do not validate PostgreSQL concurrent row locking; the management guard locks the
SUPER_ADMIN role row until transaction completion to serialize membership changes.
