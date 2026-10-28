# CoworkerOS Sandbox Browser

Ambiente browser isolato basato su **Playwright** e **FastAPI**, eseguito all'interno di un container Docker.  
Consente all'agente di eseguire navigazioni, ispezioni semantiche e interazioni web sicure senza toccare il desktop reale dell'utente.

---

## 1. Costruzione dell'immagine Docker (`docker build`)

Dalla cartella principale del progetto:

```bash
docker build -t coworkeros-sandbox-browser -f sandbox/Dockerfile sandbox/
```

---

## 2. Avvio del container (`docker run`)

Avvia il container esponendo la porta solo su `127.0.0.1:9333` e montando la sola cartella per i download:

```bash
docker run -d \
  --name coworker-browser-sandbox \
  -p 127.0.0.1:9333:9333 \
  -v "$(pwd)/sandbox/downloads:/app/downloads" \
  coworkeros-sandbox-browser
```

Su **Windows PowerShell**:
```powershell
docker run -d `
  --name coworker-browser-sandbox `
  -p 127.0.0.1:9333:9333 `
  -v "${PWD}/sandbox/downloads:/app/downloads" `
  coworkeros-sandbox-browser
```

> **Sicurezza**: il container ascolta esclusivamente sull'interfaccia di loopback locale `127.0.0.1`. Nessun file del sistema host è accessibile tranne la cartella di download designata.

---

## 3. Arresto e rimozione del container

Per fermare il container:
```bash
docker stop coworker-browser-sandbox
```

Per rimuovere il container:
```bash
docker rm coworker-browser-sandbox
```

Per verificare lo stato del container:
```bash
docker ps -f name=coworker-browser-sandbox
```

---

## 4. Endpoint esposti (porta 9333)

- `POST /open`: riceve `{"url": "https://..."}` e carica la pagina.
- `GET /snapshot`: restituisce l'albero di accessibilità formattato con riferimenti numerici `[ref]`.
- `POST /click`: riceve `{"ref": 1}` ed esegue il clic sull'elemento.
- `POST /type`: riceve `{"ref": 2, "text": "..."}` e compila l'elemento specificato.
- `POST /close`: chiude la sessione del browser.
