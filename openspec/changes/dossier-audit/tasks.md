# Tasks

Nog niet gebouwd. Vraag 1 bepaalt de vorm en die kan ik niet zelf beantwoorden.

## 1. Lidmaatschappen
- [ ] `dossiers.add` en `dossiers.remove` schrijven een auditrecord op het
      document, met de beller en het dossier.
- [ ] Een verwijdering vraagt een reden; een toevoeging niet. Iets ergens bij
      zetten is uit het resultaat te reconstrueren, iets weghalen niet.
- [ ] Geen toestandsovergang: een document verandert niet van staat door in een
      ander dossier te komen. Dit is een gebeurtenis, zoals `deanonymize`.

## 2. De open vraag die dit blokkeert
- [ ] **Waar hoort een hernoeming?** Het record hangt aan een document en een
      hernoeming raakt er duizend. Een record per document is eerlijk en
      onleesbaar; één record zonder document past niet in de tabel zoals hij nu
      is. Misschien is het antwoord dat dit niet in deze keten thuishoort.
- [ ] En wat te doen met een terugvulling van 791 documenten in één klap. Dat is
      correct en het maakt het spoor van die dag onleesbaar.

## 3. Waarom dit een spec vraagt en geen issue
Het verandert wat het auditspoor belooft te bevatten. Tot nu toe stonden er
stappen van de straat in en één toegangsgebeurtenis (`deanonymize`). Hier komt
een categorie bij: handelingen die veranderen wat een ander te zien krijgt
zonder dat er iets aan het document zelf gebeurt.

## De aanleiding
Ik heb vandaag 791 documenten verplaatst, negen met de hand elders gezet en één
dossier hernoemd. Wie dat over een maand nakijkt vindt de uitkomst en niet de
handeling — en de vraag die dan gesteld wordt is precies "wie heeft dit
verplaatst, en wanneer".
