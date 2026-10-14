"""Effective roles keep legacy ADMIN report checks compatible with SUPER_ADMIN."""
from urllib.parse import urlsplit


def report_menu_path(url):
    """Menu query strings and fragments do not change report page identity."""
    value = str(url or '').strip()
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/'):
        return None
    return parsed.path.rstrip('/') or '/'

def effective_roles(user):
    roles = {role.name for role in user.roles}
    if 'SUPER_ADMIN' in roles or user.is_admin or user.username == 'admin':
        roles.add('ADMIN')
    return roles


def is_super_admin(user):
    return bool(user and user.is_active and any(r.name == 'SUPER_ADMIN' for r in user.roles))


def report_menu_access(user):
    """Use current database grants rather than cached session permissions."""
    if not user or not user.is_active:
        return {'all_reports': False, 'urls': []}
    roles = effective_roles(user)
    if 'ADMIN' in roles:
        return {'all_reports': True, 'urls': []}
    permissions = roles | {
        permission.name for role in user.roles for permission in role.permissions
        if permission.name not in {'ADMIN', 'SUPER_ADMIN'}
    }
    urls = {
        report_menu_path(menu.url) for role in user.roles for menu in role.menus
        if report_menu_path(menu.url)
        and (not menu.permission_required or menu.permission_required in permissions)
    }
    return {'all_reports': False, 'urls': sorted(urls)}
