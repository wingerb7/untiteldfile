# Codex-prompt 2 — Visuele verbeteringen (Football Manager-stijl + analyse-laag)

> Plak dit in Codex. Scope: **alleen de beelden**. Stem, ondertiteling en muziek komen later — niet nu bouwen. We bouwen voort op de bestaande render (`possession_52_annotated_tracking_fixed.mp4`) van possession 52, match 3869685 (Argentinië–Frankrijk, WK-finale 2022).

---

## Doel
De huidige render is een nette tracking-replay. Til hem naar (a) een **herkenbare Football Manager-look** en (b) een echte **tactische analyse** in plaats van alleen bewegende stippen.

## Kunst-richting: Football Manager 2D-match-engine / tactiekbord
Maak het visueel herkenbaar als de FM 2D-wedstrijdweergave / Analysis-tab:
- **Spelers = kit-gekleurde schijven met rugnummer** in het midden (klein, vet, leesbaar). Twee duidelijk verschillende kleuren per team; dunne donkere rand. Bij sleutelspelers een klein naamlabel onder de schijf.
- **Veld** in FM-stijl: klassiek groen met subtiele **maaistrepen** (mowing stripes), strakke witte lijnen.
- **Bewegings-"staartjes"**: elke bewegende speler krijgt een korte, vervagende motion-trail achter zich (zoals FM's richtingsindicatie) — geen lange comeetstaarten.
- **Bal** als aparte, duidelijke marker (behoud de gele bal + vector).
- **Analyse-overlays** in FM Analysis-stijl: loop-pijlen (gebogen/gestippeld), passlijnen, en gearceerde zones voor ruimte.

## Behouden (niet slopen)
De sterke elementen die er al zijn: gele bal + pass/schotvector, witte ring om de ontvanger, actielabel onderin, voortgangsbalk, en **xG bij het schot**. Deze blijven.

## Verbeteringen — geprioriteerd

**1. Tactische annotatie-laag (belangrijkste).**
Voeg een laag toe die de analyse vertelt, gestuurd door een **apart, handgeschreven annotatie-bestand** (`annotations/possession_52.json`) — niet automatisch, want dit is de redactionele keuze. Ondersteun deze annotatie-types, elk met een start/eind-tijd zodat ze synchroon verschijnen:
- `run_arrow` — gebogen pijl voor een loopactie (bijv. de inloop van Di María, de derde-man-loop van Álvarez).
- `space_zone` — half-transparante gearceerde zone voor ontstane ruimte.
- `player_highlight` — pulserende ring om een speler (de derde man / vrije man).
- `pass_highlight` — accentueer een specifieke pass (de lange diagonaal).
- `text_callout` — kort tekstlabel op een positie ("vrije man", "ruimte").

Voorbeeld-schema:
```json
{ "possession": 52,
  "annotations": [
    { "kind": "player_highlight", "t_start": 6.5, "t_end": 9.0, "x": 63, "y": 68, "label": "derde man: Álvarez" },
    { "kind": "pass_highlight",   "t_start": 8.5, "t_end": 10.5, "from": [63,68], "to": [99,55], "label": "switch of play" },
    { "kind": "run_arrow",        "t_start": 9.0, "t_end": 12.5, "path": [[105,40],[112,32]], "label": "Di María loopt vrij in" },
    { "kind": "space_zone",       "t_start": 9.0, "t_end": 12.0, "polygon": [[95,25],[120,25],[120,45],[100,45]], "label": "ruimte achter de backline" }
  ] }
```
Coördinaten StatsBomb 120×80. Houd de render-code generiek: hij leest het annotatie-bestand en tekent; de inhoud staat los van de logica.

**2. Kijker-hook (eerste 2 seconden).**
Vervang de interne titel "POSSESSION 52" door een **kijkergerichte opening**: bevries ~2s op een sleutelmoment met een korte, vette regel (bijv. "Waarom stond Di María helemaal vrij?"). De hook-tekst komt uit de config, niet hardcoded.

**3. Camera-zoom / actie volgen.**
Nu is de helft van het veld leeg. Laat de "camera" dynamisch **inzoomen op de actiezone**: bepaal per frame een bounding box rond de bal + actieve spelers en crop/zoom daar soepel naartoe (met marge en easing), i.p.v. het hele veld statisch te tonen. Zorg dat het niet schokkerig springt.

**4. Bewegingspolish.**
- Gebruik **easing** (smootherstep) bij interpolatie tussen de 360-snapshots i.p.v. lineair — minder "zweverig".
- **Sync het actielabel en de bal**: het label mag niet vooruitlopen op de balpositie (dat gebeurt nu rond de lange diagonaal).
- Voeg de FM-motion-trails toe (punt 1 van de kunst-richting).

## Acceptatiecriteria
- Spelers zijn genummerde kit-schijven op een FM-achtig gestreept veld.
- `annotations/possession_52.json` bestaat en de render tekent die annotaties synchroon; de aanval toont minstens: de derde-man-highlight, de switch of play, en Di María's vrije inloop + de ruimte.
- Er is een hook van ~2s aan het begin.
- De weergave zoomt mee met de actie; geen grote dode velddelen meer.
- Beweging is merkbaar soepeler; label en bal lopen synchroon.
- Bal-vector, ontvanger-ring, actielabel, voortgangsbalk en xG blijven werken.

## Architectuur
Houd **render-logica, brand-config en annotatie-content gescheiden** (`config.yaml` voor stijl/kleuren, `annotations/*.json` voor de tactische content per aanval). Zo hergebruiken we dit straks voor andere aanvallen zonder de code aan te raken.

## Buiten scope (later)
Stem/voiceover, ondertiteling, muziek. Niet bouwen.
