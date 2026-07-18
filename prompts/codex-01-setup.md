# Codex-prompt 1 — Fundament + data + baseline-render

> Plak dit in Codex. Dit is stap 1 van meerdere. Doel: projectstructuur, StatsBomb-data ophalen, en één statische baseline-render van één aanval. Nog géén animatie, annotaties of voice — die komen in latere prompts.

---

## Context
We bouwen een pipeline die uit StatsBomb **event-data** korte, tactisch-analytische voetbalvideo's maakt (9:16, top-down). Regels: alleen eigen data-gedreven visualisaties, nooit broadcast-footage. Dit is de eerste bouwstap.

## Opdracht
Zet een Python-project op dat:

1. **Projectstructuur** aanmaakt:
   ```
   ingest.py          # data ophalen
   render/passmap.py  # baseline render
   config.yaml        # match_id, possession_id, brand-kleuren
   data/              # opgeslagen JSON
   renders/           # output-beelden
   requirements.txt
   ```

2. **Data ophaalt** met `statsbombpy`: match **3869685** (Argentinië–Frankrijk, WK-finale 2022), zowel events als 360-data. Isoleer **possession 52** (het doelpunt van Di María). Schrijf de aanval-sequentie weg naar `data/possession_52.json`: per event `type`, `player`, `timestamp`, `location`, `pass_end_location`, en de bijbehorende 360 `freeze_frame` (spelersposities).
   - Ter controle, de aanval is: Molina → Mac Allister → Messi → Álvarez → Mac Allister (lange diagonaal naar rechts) → Di María → goal. 7 passes, ~10 seconden, xG 0.30.

3. **Baseline render** maakt in `render/passmap.py` met **mplsoccer** (`VerticalPitch`, `pitch_type="statsbomb"`, heel veld):
   - genummerde passes (blauw, comet-lijn), carries (wit gestippeld), het schot (geel) + een ster op de goal;
   - de verdedigers uit de 360 freeze-frame van het schot als rode stippen;
   - merk-stijl uit `config.yaml`: donkergroen veld, geel/wit accent, titel "WHY THIS WORKED", subtitel met wedstrijd, en bronvermelding "Data: StatsBomb";
   - output als PNG in **9:16 / portret**, opgeslagen in `renders/passmap.png`.

## Tech
Python 3, `statsbombpy`, `mplsoccer`, `matplotlib`. Zet dependencies in `requirements.txt`. Houd **renderlogica en brand-config strikt gescheiden** — we voegen hier later spelersbeweging, annotaties en voice aan toe, dus de coördinaten (StatsBomb 120×80) en kleuren mogen niet in de renderfunctie hardgecodeerd staan.

## Acceptatiecriteria
- `python ingest.py` schrijft `data/possession_52.json` (13 events, met 360-frames).
- `python render/passmap.py` leest die JSON + `config.yaml` en schrijft een leesbare `renders/passmap.png` die klopt met de sequentie (pass 1 diep in eigen helft, afwerking bij de goal).
- Geen externe beelden of footage — puur data-gedreven.

## Valkuilen
- Coördinaten zijn StatsBomb **120×80** (veld-lengte × breedte).
- `freeze_frame`-punten hebben `teammate`-vlaggen relatief aan de baluitvoerder; verdedigers = `teammate: false`.
- Mocht `statsbombpy` in jouw omgeving netwerk-geblokkeerd zijn (`raw.githubusercontent.com`), val dan terug op een **sparse git clone** van `github.com/statsbomb/open-data` en laad de match-JSON's lokaal. Op een normale machine werkt `statsbombpy` gewoon direct.

## Nog niet doen (volgende prompts)
Spelersbeweging animeren (interpoleren tussen 360-frames), annotatielaag (loop/ruimte/derde man), voiceover + captions, video-assembly. Bouw de code zó dat dit er straks bovenop past.
