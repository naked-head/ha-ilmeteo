<p align="center">
  <img src="images/logo.png" alt="iLMeteo.it" width="120">
</p>

# iLMeteo.it — Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/naked-head/ha-ilmeteo.svg)](https://github.com/naked-head/ha-ilmeteo/releases)
[![Validate](https://github.com/naked-head/ha-ilmeteo/actions/workflows/validate.yml/badge.svg)](https://github.com/naked-head/ha-ilmeteo/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/naked-head/ha-ilmeteo.svg)](LICENSE)

Integrazione per [Home Assistant](https://www.home-assistant.io/) che espone i dati meteo di **[iLMeteo.it](https://www.ilmeteo.it/)** come entità `weather` native, con previsioni **giornaliere** e **orarie** (triorarie) — come le integrazioni OpenWeatherMap o Met.no.

> **Come funziona:** l'API REST ufficiale di iLMeteo è riservata a clienti business. Questa integrazione usa invece il **box previsioni pubblico e gratuito** che iLMeteo mette a disposizione per l'embedding su siti terzi (`ilmeteo.it/box/previsioni.php`), facendone il parsing lato server. Nessun token richiesto.

---

## ⚠️ Note importanti

- Questa integrazione fa **scraping** di una pagina pubblica. Non esiste alcuna garanzia contrattuale di stabilità: se iLMeteo cambia il markup del box, il parser potrebbe richiedere un aggiornamento.
- Per rispetto dei [termini d'uso](https://www.ilmeteo.it/portale/termini_e_condizioni) di iLMeteo, l'integrazione espone l'attribuzione "Dati meteo forniti da iLMeteo.it" sull'entità ed effettua il polling a bassa frequenza (ogni 30 minuti).
- Progetto non ufficiale, non affiliato a iLMeteo Srl.
- Il logo e il marchio "iLMeteo" sono di proprietà di iLMeteo Srl e sono usati al solo scopo identificativo del servizio dati.

---

## Funzionalità

- Entità `weather` nativa con condizioni attuali (slot triorario più vicino all'ora corrente)
- **Forecast giornaliero** fino a 6 giorni (temp. min/max, precipitazioni cumulate, vento)
- **Forecast orario** (triorario): 5 fasce al giorno con temperatura, temperatura percepita, umidità, vento, precipitazioni
- Distinzione automatica giorno/notte per le condizioni (es. `sunny` → `clear-night`)
- Supporto **multi-località**: ogni codice città è un'istanza separata
- Configurazione tramite UI, nessun YAML, nessun token

---

## Installazione

### Tramite HACS (consigliato)

1. HACS → Integrazioni → menu ⋮ → **Repository personalizzati**
2. Aggiungi `https://github.com/naked-head/ha-ilmeteo`, categoria **Integration**
3. Cerca "iLMeteo" e installa
4. Riavvia Home Assistant

### Manuale

1. Scarica l'ultima [release](https://github.com/naked-head/ha-ilmeteo/releases/latest)
2. Copia `custom_components/ilmeteo` in `/config/custom_components/`
3. Riavvia Home Assistant

---

## Configurazione

1. **Impostazioni → Integrazioni → Aggiungi integrazione → iLMeteo.it**
2. Seleziona **regione**, poi **provincia**, poi **comune** dai menu a tendina
3. Fatto: l'entità viene creata e validata automaticamente

L'elenco dei comuni italiani (8.218 comuni, 110 province, 20 regioni) è incluso
nell'integrazione, quindi non serve cercare codici manualmente. Per aggiungere
più località, ripeti la procedura.

> Il dataset è generato dai codici ufficiali iLMeteo tramite
> `scripts/build_locations.py` e salvato compresso (~67 KB) in
> `custom_components/ilmeteo/data/locations.json.gz`.

## Dati esposti

**Condizioni attuali:** `temperature`, `apparent_temperature`, `humidity`, `wind_speed`, `wind_bearing`, `condition`

**Forecast giornaliero:** per ogni giorno → temperatura max/min, precipitazioni totali, vento massimo, condizione rappresentativa (fascia delle 14:00)

**Forecast orario:** per ogni fascia trioraria → temperatura, percepita, umidità, vento, precipitazioni, condizione

---

## Sviluppo e test

Il parser HTML è isolato in `api.py` (`parse_box`) senza dipendenze da Home Assistant, quindi è testabile direttamente:

```bash
python tests/test_parser.py
```

I test usano un fixture HTML reale in `tests/fixtures/`.

---

## Changelog

### v0.3.0
- Selezione località a cascata: regione → provincia → comune (no codici manuali)
- Dataset di 8.218 comuni italiani incluso (JSON compresso, ~67 KB)
- Script di rigenerazione dataset in `scripts/build_locations.py`

### v0.2.0
- Riscrittura completa: backend basato sul box widget pubblico (no API token)
- Forecast giornaliero + orario
- Distinzione giorno/notte
- Test unitari del parser

### v0.1.0
- Prima bozza basata sull'API REST (poi resa enterprise-only)

---

## Licenza

MIT — vedi [LICENSE](LICENSE)
