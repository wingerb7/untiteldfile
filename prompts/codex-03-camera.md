# Codex-prompt 3 — Camera/viewport: aanval voetbalinhoudelijk begrijpelijk maken

> Scope: **uitsluitend camera-/viewportlogica.** Niet wijzigen: tracking, interpolatie, patroondetectie, speler-ID's, rendering-geometrie, tactische analyse, scene-selectie.

---

## Probleem
Na de pass van Locatelli op Berardi verdwijnt Locatelli uit beeld. Zijn loopactie is niet zichtbaar, waardoor hij vlak voor het schot uit het niets lijkt te verschijnen. De kijker mist de relatie tussen pass → overlap → cutback.

## Doel
De volledige aanval is in één vloeiende sequentie begrijpelijk zonder uitleg.

## Waar het zit
Alle relevante logica staat in **`apply_camera()` in `src/pipelines/render_analysis.py`** (rond regel 205–244). Die functie wordt per frame aangeroepen vanuit `render_scene_plan()`.

## Concrete oorzaken (geanalyseerd)

**1. De framing-set kent geen geheugen en geen vooruitblik.** `apply_camera` verzamelt nu: de bal, `event.start_location`, `event.end_location`, spelers **binnen 34 m van de bal** (`np.hypot(...) <= 34.0`), plus actieve annotatiepunten. Zodra Locatelli de bal wegspeelt en Berardi wegdribbelt, valt Locatelli buiten die 34 m-straal en dus buiten beeld. Er is geen mechanisme dat de vórige baldrager vasthoudt of dat vooruitkijkt naar waar de bal heen gaat.

**2. De viewport wordt hard op de veldgrenzen geklemd**, waardoor de actie naar de beeldrand wordt geduwd:
```python
center_x = min(80.0 - width / 2.0, max(width / 2.0, center_x))
...
ax.set_xlim(max(-3.0, camera["x"] - width / 2.0), min(83.0, camera["x"] + width / 2.0))
```
Bij spel dicht op de zijlijn kan het midden niet meeschuiven, met als gevolg dat de bal half buiten beeld valt (zichtbaar rond seconde 5 van de huidige render).

**3. Vaste easing** (`camera_ease`, nu 0.08) reageert bij snelle omschakelingen te traag, en `height` is gecapt op 124.0.

## Gewenst gedrag
- Houd zowel de baldrager als de belangrijkste aanvallende loopactie in beeld.
- Nadat Locatelli inspeelt op Berardi blijft Locatelli zichtbaar terwijl hij doorloopt richting het strafschopgebied.
- Tijdens Berardi's dribbel mag/moet de viewport uitzoomen of verschuiven zodat beide spelers zichtbaar blijven.
- Bij de cutback is Locatelli al in beeld vóórdat hij de bal ontvangt.
- Geen abrupte camerabewegingen of plotselinge verschijningen.

## Voorgestelde aanpak (camera-only)
Bouw in `apply_camera` een **narratieve focus-set** in plaats van de huidige bal-centrische set:

1. **Altijd**: balpositie + huidige actor.
2. **Nalooptijd (linger)**: de locatie van de vorige event-actor blijft nog ~2,5–3,5 s meetellen nadat hij de bal heeft gespeeld. Zo blijft de zone waar Locatelli vertrekt in beeld.
3. **Vooruitblik (lookahead)**: neem de `start_location` van de **komende events** binnen een horizon van ~2,5–3,5 s mee (die staan in het scene-plan/timeline: `renders/second_goal_short_scene_plan.json`, `renders/second_goal_short_timeline.json`). Daardoor komt het cutback-punt in beeld vóórdat de bal er is, en zit de loopcorridor van Locatelli automatisch in kader.
4. **Zachte intrede**: laat lookahead-punten geleidelijk meewegen (gewicht 0→1 naarmate ze naderen) in plaats van in één frame te verschijnen, zodat de camera niet springt.
5. **Overscan toestaan**: laat de viewport buiten de veldgrenzen uitsteken (bijv. x ∈ [−8, 88], y ∈ [−8, 128]) in plaats van hard te klemmen, zodat de bal gecentreerd kan blijven bij spel op de zijlijn.
6. **Harde garantie**: na berekening moet de bal altijd binnen een veiligheidsmarge van het beeld liggen; corrigeer het centrum indien nodig vóór de easing.
7. **Adaptieve easing**: bij grote doelverschuivingen iets sneller easen, bij kleine langzamer — vloeiend maar niet traag. Sta een ruimere `height` toe wanneer meerdere focuspunten ver uit elkaar liggen.

Maak de nieuwe parameters configureerbaar onder `animation:` in `config.yaml` (bijv. `camera_linger_seconds`, `camera_lookahead_seconds`, `camera_overscan`, `camera_ease_min/max`), met defaults die het huidige gedrag niet elders breken.

## Belangrijke waarschuwing (lees dit vóór je begint)
Tussen Berardi's balaanname (00:25:15,0) en zijn pass (00:25:21,6) zit een **gat van 6,6 seconden zonder enige StatsBomb 360-momentopname**. In die periode bestaat er voor veel spelers simpelweg geen positiedata. Camera-werk kan de juiste **zone** in beeld houden, maar kan een speler niet zichtbaar maken die door de tracking is weggevallen.

Dat betekent: het criterium *"Locatelli blijft na zijn pass visueel te volgen"* is met camera-only wijzigingen mogelijk **niet volledig haalbaar**. Rapporteer expliciet in hoeverre het lukt. Als blijkt dat de beperking bij de tracking ligt, **los dat niet op** — meld het alleen, dan pakken we het in een aparte opdracht op.

## Acceptatiecriteria
- Locatelli blijft na zijn pass zoveel mogelijk visueel te volgen (zie waarschuwing hierboven).
- Berardi en Locatelli zijn tijdens de beslissende fase gelijktijdig zichtbaar waar de data dat toelaat.
- De cutback is direct begrijpelijk.
- De bal valt nooit (deels) buiten beeld.
- De video blijft kort (±10–20 s).
- Alle bestaande tests blijven slagen (`pytest`).

## Output
Genereer opnieuw: **`renders/second_goal_short.mp4`**

## Rapporteer
1. Welke viewport-/camera-algoritmen zijn aangepast (en met welke parameters).
2. Welke bestanden zijn gewijzigd.
3. Expliciete bevestiging dat tracking, interpolatie, detectie, speler-ID's en tactische analyse **ongewijzigd** zijn.
4. In hoeverre Locatelli daadwerkelijk volgbaar is, en of de 360-datagap daarbij beperkend was.

## Let op — huidige staat van het bestand
In `src/pipelines/render_analysis.py` zijn eerder al drie wijzigingen gedaan: (a) `draw_player_disc` tekent geen rugnummers/naamlabels meer (schone gekleurde schijven), (b) `render_scene_plan` heeft optionele parameters `frames_dir` en `frame_range` voor batch-rendering naar PNG's, (c) de score-`label` in `config.yaml` is gecorrigeerd. Laat die intact.
