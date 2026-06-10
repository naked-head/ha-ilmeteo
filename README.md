<<<<<<< HEAD
# ha-ilmeteo
=======
# iLMeteo.it — Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/naked-head/ha-ilmeteo.svg)](https://github.com/naked-head/ha-ilmeteo/releases)
[![GitHub License](https://img.shields.io/github/license/naked-head/ha-ilmeteo.svg)](LICENSE)
[![Maintainer](https://img.shields.io/badge/maintainer-%40naked--head-blue.svg)](https://github.com/naked-head)

Integrazione per [Home Assistant](https://www.home-assistant.io/) che espone i dati meteo di **[iLMeteo.it](https://www.ilmeteo.it/)** come entità `weather` native, con supporto a previsioni giornaliere multi-giorno — esattamente come le integrazioni OpenWeatherMap o Met.no.

> **Nota:** questa integrazione richiede un token API iLMeteo. Il servizio API è gestito da [Nohup Srl](https://www.nohup.it/) per conto di iLMeteo.it ed è accessibile su richiesta all'indirizzo [apigateway.ilmeteo.it](https://apigateway.ilmeteo.it).

---

## Funzionalità

- Entità `weather` nativa con condizioni attuali
- Previsioni giornaliere fino a 7 giorni (temperatura min/max, precipitazioni, vento, umidità)
- Supporto **multi-località**: ogni città aggiunta diventa un'istanza separata
- Configurazione tramite UI (nessun YAML richiesto)
- Aggiornamento automatico ogni ora

---

## Installazione

### Tramite HACS (consigliato)

1. Apri HACS in Home Assistant
2. Vai su **Integrazioni** → menu ⋮ → **Repository personalizzati**
3. Aggiungi `https://github.com/naked-head/ha-ilmeteo` con categoria **Integration**
4. Cerca "iLMeteo" in HACS e installa
5. Riavvia Home Assistant

### Manuale

1. Scarica l'ultima [release](https://github.com/naked-head/ha-ilmeteo/releases/latest)
2. Copia la cartella `custom_components/ilmeteo` in `/config/custom_components/`
3. Riavvia Home Assistant

---

## Configurazione

1. Vai in **Impostazioni → Integrazioni → Aggiungi integrazione**
2. Cerca **iLMeteo.it**
3. Inserisci il **token API** e il nome della città da cercare
4. Seleziona la località esatta tra i risultati
5. Ripeti il processo per aggiungere altre città

---

## Struttura entità

Ogni località configurata genera un'entità:

```
weather.ilmeteo_<nome_citta>
```

Con i seguenti attributi:

| Attributo | Descrizione |
|---|---|
| `temperature` | Temperatura attuale (°C) |
| `humidity` | Umidità relativa (%) |
| `wind_speed` | Velocità del vento (m/s) |
| `wind_bearing` | Direzione del vento (°) |
| `pressure` | Pressione atmosferica (hPa) |
| `condition` | Condizione meteo (stringa HA standard) |
| `forecast` | Lista previsioni giornaliere |

---

## Changelog

### v1.0.0
- Prima release pubblica
- Entità `weather` con previsioni giornaliere
- Config flow UI con ricerca località
- Supporto multi-istanza

---

## Licenza

MIT — vedi [LICENSE](LICENSE)
>>>>>>> 52b76dc (Initial release v1.0.0)
