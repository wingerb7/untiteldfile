# Analyse van twee doelpunten — bevindingen en oplossing

*Di María (Argentinië–Frankrijk, WK-finale 2022) en Locatelli (Italië–Zwitserland, EK 2020)*
*Opgesteld op basis van de renders, de fidelity-sheets, de onderliggende StatsBomb-data en de code in de repository.*

---

## 1. Wat er goed werkt

Voordat de problemen: er staat iets dat werkt, en dat is niet vanzelfsprekend.

**De pipeline generaliseert.** Dezelfde keten draait op twee verschillende wedstrijden, competities en jaren zonder dat er iets is hardgecodeerd. Dat is structureel het belangrijkste dat er tot nu toe is bereikt.

**De tactische detectie doet echt werk.** De line-break-detector vindt zelfstandig het beslissende moment, onderbouwt het met bewijs (voorwaartse progressie, gepasseerde verdedigers, positie van de verdedigingslijn) en levert een annotatie inclusief gestippelde verdedigingslijn, correct getimed. Bij Locatelli produceerde hij zelf de zin *"Manuel Locatelli breaks the line into the runner."*

**De narratieve selectie werkt.** Uit een possession van 58,6 seconden (die begint bij keeper Donnarumma) wordt automatisch een venster van 11 seconden gekozen dat het doelpunt bevat. Dat is precies de juiste beweging.

**De datagetrouwheid op event-momenten is aantoonbaar in orde.** In de fidelity-sheets zijn ruwe 360-data, genormaliseerde data en renderer-state visueel identiek — zelfde spelers, posities en keeper-markers. Normalisatie en renderer vervormen niets op de momenten die daadwerkelijk zijn waargenomen.

---

## 2. Bevindingen per doelpunt

### 2.1 Di María — Argentinië–Frankrijk, WK-finale 2022

De aanval: Molina → Mac Allister → Messi → Álvarez → Mac Allister (verlegd naar rechts) → Di María → doelpunt. Zeven passes, ongeveer tien seconden, xG 0,30. De data is dicht: alle dertien events hebben een 360-frame, met 8 tot 20 zichtbare spelers.

Wat er misging:

- **De score klopte niet.** De ondertitel meldde "Argentina 3-3 France". Op het moment van dít doelpunt stond het 2-0 (Messi penalty 23', Di María 36'); 3-3 was de eindstand ná verlenging. De regel stond hardgecodeerd in `config.yaml`.
- **De rugnummers waren verzonnen.** `jersey_number()` leidt een nummer af uit het interne tracking-ID via `((suffix - 1) % 99) + 1`. Er komen nummers uit die niemand draagt. De oorzaak is fundamenteel: StatsBomb 360-frames bevatten geen spelersidentiteit — alleen anonieme posities met een vlag voor eigen team, tegenstander of keeper. Alleen de speler áán de bal is bij naam bekend.
- **De annotatielaag was onleesbaar.** Op het beslissende moment stapelden vier tot zes tekstkaders over elkaar en over de spelersschijven. De hoofdtitel overlapte de ondertitel.
- **Alle annotaties stonden vanaf het eerste frame in beeld**, omdat de hook twee seconden bevriest op modeltijd 9,35 s en dus de late toestand toont.
- **De speler-identiteit klopte niet op het beslissende moment**: de vrije man die inloopt en scoort is Di María, maar het label bij die gemarkeerde speler zei "Allister".
- **De camera duwde de bal naar de beeldrand** en zoomde bij de afwerking niet in.
- **Eén speler werd buiten het veld getekend** (sheet 02, marker 14) — een coördinaat buiten de veldgrenzen die stilzwijgend buiten de assen belandt.
- **Het geselecteerde moment viel buiten het venster.** In de fidelity-sheets staat Molina's pass (2112,89) als `selected_finding`, terwijl `window_start` op 2114,357 ligt. De pass waar de analyse op rust valt dus vóór de clip begint. In de huidige repo is de selectie verschoven naar Mac Allister's pass (2114,357), die wél binnen het venster ligt — dus óf de sheets zijn verouderd, óf de selectie is instabiel tussen runs.

### 2.2 Locatelli — Italië–Zwitserland, EK 2020

De aanval: Immobile → Locatelli → lijnbrekende pass op Berardi → Berardi dribbelt rechts → cutback → Locatelli scoort, xG 0,741. Venster van 11,0 voetbalseconden, render 13,8 seconden.

Wat er misging:

- **De spelers verdwijnen op het beslissende moment.** Bij Locatelli's afwerking is het veld leeg op één schijfje na. Dit is géén databeperking: het 360-frame bij dat schot bevat **elf spelers**, en de fidelity-sheets bevestigen dat die elf correct door de hele keten komen. De oorzaak zit in de tracking. Tussen Berardi's balaanname (1515,044) en zijn pass (1521,636) zit een **gat van 6,6 seconden zonder enige 360-momentopname** — hij dribbelt. Met `max_missing_snapshots: 1` en `maximum_speed_mps: 9.5` kan de tracker spelers niet over dat gat koppelen; sporen sterven af, nieuwe worden geboren, en alles onder confidence 0,35 valt uit de render. De audit bevestigt dit met een hard cijfer: **75 tracks aangemaakt voor maximaal ongeveer 8 tegen 8 zichtbare spelers**.
- **Daardoor is Locatelli's loopactie onzichtbaar.** Hij speelt in, verdwijnt, en duikt vlak voor het schot uit het niets op. De kijker mist het verband tussen pass, doorloop en cutback — precies waardoor de aanval voetbalinhoudelijk onbegrijpelijk blijft.
- **De score klopte weer niet, op dezelfde manier**: "Italy 3-0 Switzerland" bij het **eerste** doelpunt, terwijl het toen 1-0 was (Locatelli 26' en 52', Immobile 89').
- **Dezelfde verzonnen rugnummers** (51, 52, 55, 61, 72, 73, 74).
- **De camera faalt op twee manieren**: rond seconde 5 valt de bal half buiten beeld doordat het beeld hard op de veldgrenzen wordt geklemd, en bij het schot zoomt hij niet in — de actie is een stipje in een voor tachtig procent leeg beeld.
- **De clip opent bij de tegenstander**: Xhaka neemt de bal aan terwijl eronder "Italy reconstruction" staat.

### 2.3 Wat de fidelity-sheets zelf laten zien

De sheets zijn waardevol, maar hebben twee eigen gebreken.

**De legenda verschilt per paneel.** In Raw en Normalized is geel de speler aan de bal; in het Renderer-paneel is geel de bál. In sheet 01 van Locatelli staat daardoor op Immobile's plek een blauwe schijf terwijl de gele marker tien meter verderop ligt. Waarschijnlijk geen positiefout, maar als controle-instrument onbruikbaar: je ziet een marker verspringen en kunt niet zien of dat een bug is of een kleurbetekenis. Daar hangt een tweede vraag aan: op het moment van de pass hoort de bal nog aan de voet te liggen, niet tien meter verderop — dus het is niet gegarandeerd dat de drie panelen hetzelfde tijdstip tonen.

**Twee van de vier samples zijn hetzelfde moment.** Bij Locatelli hebben event 03 en 04 exact dezelfde timestamp (1522,263).

En het fundamentele punt: **de sheets bemonsteren uitsluitend event-frames** — precies de momenten waar nooit iets misging. Elk werkelijk probleem zit *tussen* de events. Het harnas valideert de veilige helft en slaat de risicovolle over.

---

## 3. De vier foutklassen

Alles hierboven valt terug op vier oorzaken. Dat is de kern van deze analyse: het zijn geen dertien losse bugs.

**Klasse 1 — Verzonnen waarden waar data zou moeten gelden.**
Rugnummers afgeleid uit tracking-ID's; scoreregel met de hand ingetypt. Beide fout, beide herhalen zich bij élke nieuwe video. De 360-data kent geen spelersidentiteit, dus echte nummers zijn onverkrijgbaar; de score is wél afleidbaar uit de wedstrijddata op dat tijdstip.

**Klasse 2 — De keten gaat slecht om met dunne of ontbrekende data.**
Lange snapshot-gaten doden tracks, waardoor het veld leegloopt op precies het moment dat ertoe doet. Spelers onder de confidence-drempel verdwijnen zonder spoor. En wat wél gereconstrueerd wordt, is in beeld niet te onderscheiden van wat echt is waargenomen.

**Klasse 3 — De camera dient het verhaal niet.**
De bal valt buiten beeld, er wordt niet ingezoomd op de climax, en de belangrijkste speler zónder bal verdwijnt uit kader. De parameters om dit op te lossen (`camera_lookback_seconds`, `camera_lookahead_seconds`) bestaan al in de code maar staan op `0.0` en zijn niet in de config gezet.

**Klasse 4 — Het QA-harnas controleert het veilige geval.**
Alleen event-frames, inconsistente legenda, dubbele timestamps, labels op array-index in plaats van identiteit, geen numeriek oordeel, geen narratieve invarianten.

**En operationeel:** de repository staat **niet onder versiebeheer**. Dat is geen theoretisch risico — het heeft al toegeslagen: de verwijdering van de verzonnen rugnummers is stilzwijgend overschreven en `jersey_number()` wordt weer aangeroepen.

---

## 4. De oplossing, op volgorde

**Stap 0 — Zet het onder versiebeheer. Vandaag.**
`git init` en committen. Vijf minuten. Zonder dit overschrijven twee agents elkaars werk zonder dat iemand het merkt, zoals al is gebeurd. Alles hieronder is riskant zolang dit niet staat.

**Stap 1 — Klasse 2: repareer de continuïteit over lange gaten.**
Dit eerst, want het breekt de climax van beide video's, en géén camerawerk kan een speler tonen die niet bestaat. Concreet: overbrug bekende identiteiten over gaten langer dan één snapshot in plaats van het spoor te beëindigen; behoud de laatst bekende positie in plaats van de speler te verwijderen; en maak onzekerheid zichtbaar in de render (bijvoorbeeld geïnterpoleerde spelers met een open rand of lagere dekking). Dat lost meteen het integriteitsbezwaar op: je toont dan niet langer afgeleide beweging alsof ze waargenomen is.

**Stap 2 — Klasse 3: camera als verteller.**
Zet de bestaande lookback- en lookahead-parameters aan en bouw een narratieve focus-set: bal, huidige actor, de vórige actor die nog enkele seconden meetelt, en de locaties van de kómende events. Sta overscan buiten de veldgrenzen toe zodat de bal gecentreerd kan blijven, garandeer hard dat de bal binnen een veiligheidsmarge valt, en gebruik adaptieve easing. Pas ná stap 1 is het criterium "Locatelli blijft volgbaar" haalbaar.

**Stap 3 — Klasse 1: laat data de waarden bepalen.**
Leid de scoreregel af uit de wedstrijddata op het tijdstip van het doelpunt in plaats van hem in te typen. Verwijder de rugnummers definitief — spelers worden schone gekleurde schijven, zoals besloten. Regel: toon nooit een waarde die niet uit data volgt of expliciet per video is geschreven; is hij niet af te leiden, toon hem dan niet.

**Stap 4 — Klasse 4: maak van het harnas een poort.**
Bemonster geïnterpoleerde frames, met nadruk op het midden van de grootste snapshot-gaten — daar zitten de fouten. Maak de legenda identiek over de panelen en teken de bal als eigen vorm. Print en assert het modeltijdstip per paneel. Ontdubbel samples binnen enkele milliseconden. Label op stabiele identiteit. Voeg numerieke assertions toe (maximale positieafwijking, aantallen per stap, PASS/FAIL) en leg de narratieve invarianten vast als test: het geselecteerde moment ligt binnen het venster, het venster bevat het doelpunt, de duur valt binnen de doelrange. Daarna bewaakt het harnas stap 1 tot en met 3 vanzelf.

---

## 5. Wat hier expliciet niet nodig is

Geen van deze vier klassen vraagt om een Football Action Graph, een tactische actie-taxonomie of een herschreven Narrative Builder. Het zijn allemaal reparaties binnen de bestaande architectuur. De audit meet de repository terecht af tegen een eindstaat, maar die eindstaat is pas relevant wanneer je op volume gaat automatiseren — en dat is bewust uitgesteld tot het format bewezen is. Wat de Di María-video inhoudelijk leesbaar maakte waren handmatige annotaties, en dat blijft voorlopig ook de bedoeling.

---

## 6. Samengevat

De tactiek-analyse en de narratieve selectie werken al. De data komt getrouw door de keten heen op de momenten die zijn waargenomen. Wat de video's onbegrijpelijk maakt, zit in de vier seconden dáártussen — waar spelers verdwijnen, de camera de verkeerde kant op kijkt, en het controle-instrument niet meekijkt. Repareer de continuïteit, laat de camera het verhaal volgen, haal de verzonnen waarden eruit en laat het harnas oordelen. In die volgorde.
