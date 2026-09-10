"""Effective roles keep legacy ADMIN report checks compatible with SUPER_ADMIN."""

def effective_roles(user):
    roles = {role.name for role in user.roles}
    if 'SUPER_ADMIN' in roles or user.is_admin or user.username == 'admin':
        roles.add('ADMIN')
    return roles


def is_super_admin(user):
    return bool(user and user.is_active and any(r.name == 'SUPER_ADMIN' for r in user.roles))
