# Tarea 0: Prerrequisitos del entorno

**Archivos:** ninguno. Esta tarea prepara la máquina de desarrollo.

---

## Decisiones de diseño

**¿Por qué una tarea manual y no un script?**
- Instalar Docker requiere `sudo` y cambia la configuración del sistema: lo corre la persona, no el agente.
- Se hace una sola vez por máquina; un script versionado no aporta.

**¿Por qué `uv` instala Python 3.13 en lugar de usar el del sistema?**
- El sistema trae Python 3.12 y el proyecto fija 3.13 en `.python-version`.
- `uv` descarga el intérprete aislado, sin tocar el Python del sistema.

---

## Paso 1: Instalar uv

Run: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Después abrir una terminal nueva (o `source $HOME/.local/bin/env`).

## Paso 2: Verificar uv e instalar Python 3.13

Run: `uv --version`
Expected: `uv 0.x.y` (cualquier versión)

Run: `uv python install 3.13 && uv python find 3.13`
Expected: una ruta que termina en `python3.13`

## Paso 3: Instalar Docker Engine y el plugin Compose (Ubuntu)

Lo corre la persona en su terminal:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
```

Cerrar sesión y volver a entrar para que tome el grupo `docker`.

## Paso 4: Verificar Docker

Run: `docker run --rm hello-world`
Expected: contiene `Hello from Docker!`

Run: `docker compose version`
Expected: `Docker Compose version v2.x.y`

## Paso 5: Verificar acceso al repo

Run: `git -C /home/miguelbenitez/projects/pedidos/Pedidos_back remote -v`
Expected: `origin  https://github.com/MiguelAndresBenitez/Pedidos_back.git (fetch)`

Sin commit: esta tarea no cambia el repo.
