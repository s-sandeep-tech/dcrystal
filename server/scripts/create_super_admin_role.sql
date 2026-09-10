-- Creates the protected role only; deliberately assigns no users.
INSERT INTO roles (name, description)
VALUES ('SUPER_ADMIN', 'Protected administrator with full ADMIN access and authority over SUPER_ADMIN accounts')
ON CONFLICT (name) DO NOTHING;
