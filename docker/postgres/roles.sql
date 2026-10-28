-- Roles de Minutas. Lo ejecuta el superusuario una sola vez, sobre la base de la app.
-- Las contraseñas se fijan aparte (Docker: 02-claves.sh; tests: conftest.py).

CREATE ROLE minutas_owner LOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE minutas_app LOGIN NOSUPERUSER NOBYPASSRLS;

GRANT USAGE, CREATE ON SCHEMA public TO minutas_owner;
GRANT USAGE ON SCHEMA public TO minutas_app;

ALTER DEFAULT PRIVILEGES FOR ROLE minutas_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO minutas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE minutas_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO minutas_app;
