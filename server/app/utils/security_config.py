import os


def signing_key(name):
    value = os.environ.get(name, '')
    if len(value.strip()) < 32 or value in {
        'super-secret-key-change-me', 'dev-secret-key-123',
    }:
        raise RuntimeError(f'{name} must be configured with a random secret of at least 32 characters')
    return value


def session_is_current(user, session_data):
    version = session_data.get('session_version')
    return bool(user and user.is_active and type(version) is int
                and version == user.session_version)
