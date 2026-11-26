# Данные на VPS (не в Git)

<!-- markdownlint-disable MD013 -->

В `.gitignore`: `data/manuals/`, `data/index/`.

После локальной сборки:

```powershell
$KEY = "$env:USERPROFILE\.ssh\iikuznitsa_deploy"
$HOST = "root@5.129.222.124"
$ROOT = "/opt/iikuznitsa/iikuznitsa-digital-mechanic"
scp -i $KEY -r D:\MyProjectsCursor\iikuznitsa-digital-mechanic\data\manuals "${HOST}:${ROOT}/data/"
scp -i $KEY -r D:\MyProjectsCursor\iikuznitsa-digital-mechanic\data\index "${HOST}:${ROOT}/data/"
```

На сервере после `git pull`:

```bash
cd /opt/iikuznitsa/iikuznitsa-digital-mechanic
docker compose build web
docker compose up -d web
curl -sk https://127.0.0.1:8080/api/health
```

Ожидается `search_hybrid: true` и `embedding_vectors` > 3000.
