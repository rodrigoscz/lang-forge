# Deploy Guide - lang-forge

## Prerequisites

1. **DNS configurado en Squarespace**:
   - Type: A
   - Host: forge
   - Points to: 143.95.214.60
   - TTL: 3600

2. **Acceso SSH al VPS**:
   ```bash
   ssh root@143.95.214.60
   ```

3. **Variables de entorno locales**:
   ```bash
   export DATAFORSEO_LOGIN="tu_login"
   export DATAFORSEO_PASSWORD="tu_password"
   ```

## Deploy Steps

### 1. Primera vez: Setup en el VPS

SSH al VPS y crear el directorio:

```bash
ssh root@143.95.214.60
mkdir -p /opt/lang-forge
```

### 2. Actualizar Caddy para el nuevo subdominio

En el VPS, editar el Caddyfile:

```bash
nano /opt/caddy/Caddyfile
```

Agregar al final:

```caddyfile
forge.novasanchez.com {
    reverse_proxy localhost:8001
    
    header {
        X-Frame-Options DENY
        X-Content-Type-Options nosniff
        X-XSS-Protection "1; mode=block"
        Referrer-Policy strict-origin-when-cross-origin
    }
    
    encode gzip
    
    log {
        output file /var/log/caddy/forge.novasanchez.com.log
        format json
    }
}
```

Recargar Caddy:

```bash
docker-compose -f /opt/caddy/docker-compose.yml restart caddy
```

### 3. Deploy desde tu máquina local

```bash
cd /Users/novasanchez/lang-forge
./deploy.sh
```

El script va a:
1. Build el frontend Astro
2. Sincronizar archivos al VPS
3. Reconstruir containers Docker
4. Verificar health check

### 4. Verificar deploy

```bash
curl https://forge.novasanchez.com/health
```

Debería devolver: `{"status": "ok"}`

## Actualizaciones

Para deploys posteriores, solo correr:

```bash
./deploy.sh
```

## Troubleshooting

### Container no arranca

```bash
ssh root@143.95.214.60
cd /opt/lang-forge
docker-compose logs
```

### Caddy no sirve el sitio

```bash
ssh root@143.95.214.60
docker-compose -f /opt/caddy/docker-compose.yml logs caddy
```

### Verificar DNS

```bash
dig forge.novasanchez.com
```

Debería mostrar: `143.95.214.60`

## Rollback

Si algo sale mal:

```bash
ssh root@143.95.214.60
cd /opt/lang-forge
git log --oneline  # Ver commits anteriores
git checkout <commit-hash>
docker-compose down
docker-compose up -d --build
```

## Monitoreo

Ver logs en tiempo real:

```bash
ssh root@143.95.214.60
cd /opt/lang-forge
docker-compose logs -f
```

Ver métricas de recursos:

```bash
docker stats lang-forge
```
