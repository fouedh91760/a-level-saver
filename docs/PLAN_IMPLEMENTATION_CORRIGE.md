# Plan d'Implémentation Corrigé - Scénarios Manquants

**Date** : 2026-01-29
**Basé sur** : Audit du document `IMPLEMENTATION_SCENARIOS_MANQUANTS.md`
**Statut** : Prêt pour implémentation

---

## Résumé des Corrections

| Élément original | Problème identifié | Correction |
|------------------|-------------------|------------|
| 5 nouvelles intentions | 3 existent déjà | Seulement 2 à créer |
| Comparateurs Handlebars `(lte x 7)` | Non supportés | Flags booléens pré-calculés |
| 6 nouveaux partials | 2 existent sous autre nom | Seulement 4 à créer |
| Variables manquantes | Non documentées | Liste exhaustive ajoutée |

---

## Phase 1 : Variables et Flags (Prérequis)

### 1.1 Ajouter les flags booléens dans `state_detector.py`

**Fichier** : `src/state_engine/state_detector.py`
**Méthode** : `_build_context()`

Ajouter après le calcul de `days_until_exam` (ligne ~300) :

```python
# Flags temporels pour templates (remplacent les comparateurs non supportés)
'exam_within_7_days': days_until_exam is not None and 0 <= days_until_exam <= 7,
'exam_within_10_days': days_until_exam is not None and 0 <= days_until_exam <= 10,
'examen_pas_encore_passe': days_until_exam is not None and days_until_exam > 0,
'examen_imminent': days_until_exam is not None and 0 <= days_until_exam <= 3,

# Flag pour convocation anormale (VALIDE CMA + J-7 + pas de convoc)
'convocation_anormale': (
    evalbox == 'VALIDE CMA' and
    days_until_exam is not None and
    0 <= days_until_exam <= 7
),
```

### 1.2 Ajouter `pieces_refusees_details` dans le contexte

**Fichier** : `src/state_engine/state_detector.py`
**Méthode** : `_build_context()`

Ajouter dans la section examt3p_data (ligne ~330) :

```python
# Détails des pièces refusées (pour templates Refus CMA)
'pieces_refusees_details': examt3p_data.get('pieces_refusees_details', []),
'has_pieces_refusees': bool(examt3p_data.get('pieces_refusees_details')),
```

### 1.3 Propager les nouveaux flags dans `template_engine.py`

**Fichier** : `src/state_engine/template_engine.py`
**Méthode** : `_prepare_placeholder_data()`

Ajouter dans la section des booléens (ligne ~960) :

```python
# Flags temporels
'exam_within_7_days': context.get('exam_within_7_days', False),
'exam_within_10_days': context.get('exam_within_10_days', False),
'examen_pas_encore_passe': context.get('examen_pas_encore_passe', False),
'examen_imminent': context.get('examen_imminent', False),
'convocation_anormale': context.get('convocation_anormale', False),

# Pièces refusées
'pieces_refusees_details': context.get('pieces_refusees_details', []),
'has_pieces_refusees': context.get('has_pieces_refusees', False),
```

---

## Phase 2 : Nouvelles Intentions (2 seulement)

### 2.1 PERMIS_PROBATOIRE (I38)

**Fichier** : `states/state_intention_matrix.yaml`
**Section** : `intentions:`

```yaml
PERMIS_PROBATOIRE:
  id: "I38"
  description: "Question sur permis probatoire"
  triggers:
    - "permis probatoire"
    - "jeune permis"
    - "3 ans de permis"
    - "fin de probation"
    - "permis de moins de 3 ans"
    - "période probatoire"
  priority: 80
```

### 2.2 DATE_LOINTAINE_EXAMT3P (I39)

**Fichier** : `states/state_intention_matrix.yaml`
**Section** : `intentions:`

```yaml
DATE_LOINTAINE_EXAMT3P:
  id: "I39"
  description: "Veut une date pas encore visible sur ExamT3P"
  triggers:
    - "date pas disponible"
    - "date non visible"
    - "date pas encore"
    - "septembre"
    - "octobre"
    - "novembre"
    - "décembre"
    - "plus tard dans l'année"
    - "date plus lointaine"
  priority: 70
```

### 2.3 Intentions NON créées (existent déjà)

| Intention proposée | Utiliser à la place | ID |
|--------------------|---------------------|-----|
| DEMANDE_FACTURE_ATTESTATION | DEMANDE_CERTIFICAT_FORMATION | I32 |
| CHANGEMENT_DEPARTEMENT | DEMANDE_AUTRES_DATES | I09 |
| CHANGEMENT_SESSION | CONFIRMATION_SESSION | I13 |

---

## Phase 3 : Entrées Matrice État×Intention

### 3.1 REFUSED_CMA × DEMANDE_CONVOCATION

```yaml
"EVALBOX_REFUSE_CMA:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation mais dossier refusé CMA"
  context_flags:
    intention_demande_convocation: true
    evalbox_refus_cma: true
    show_documents_refuses: true
    show_statut_section: true
```

### 3.2 REFUSED_CMA × REPORT_DATE

```yaml
"EVALBOX_REFUSE_CMA:REPORT_DATE":
  template: "response_master.html"
  description: "Demande report mais dossier déjà refusé = report auto"
  context_flags:
    intention_report_date: true
    evalbox_refus_cma: true
    report_deja_effectue: true
    show_documents_refuses: true
```

### 3.3 DOSSIER_SYNCHRONIZED × DEMANDE_CONVOCATION

```yaml
"DOSSIER_SYNCHRONIZED:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation mais dossier en cours d'instruction"
  context_flags:
    intention_demande_convocation: true
    evalbox_dossier_synchronise: true
    show_statut_section: true
```

### 3.4 DEADLINE_MISSED × DEMANDE_CONVOCATION

```yaml
"DEADLINE_RATEE:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation mais deadline ratée = report auto"
  context_flags:
    intention_demande_convocation: true
    deadline_missed: true
    show_statut_section: true
```

### 3.5 EXAM_DATE_EMPTY × DEMANDE_CONVOCATION

```yaml
"EXAM_DATE_EMPTY:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation mais pas de date assignée"
  context_flags:
    intention_demande_convocation: true
    date_examen_vide: true
    show_dates_section: true
```

### 3.6 VALIDE_CMA × DEMANDE_CONVOCATION (convocation anormale)

```yaml
"DATE_FUTURE_VALIDE_CMA:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation - validé CMA"
  context_flags:
    intention_demande_convocation: true
    evalbox_valide_cma: true
    show_statut_section: true
```

### 3.7 PROSPECT × Intentions diverses

```yaml
"PROSPECT_UBER_20:STATUT_DOSSIER":
  template: "response_master.html"
  description: "Prospect demande statut"
  context_flags:
    intention_statut_dossier: true
    is_prospect: true
    show_statut_section: true

"PROSPECT_UBER_20:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Prospect demande convocation"
  context_flags:
    intention_demande_convocation: true
    is_prospect: true

"PROSPECT_UBER_20:DEMANDE_IDENTIFIANTS":
  template: "response_master.html"
  description: "Prospect demande identifiants"
  context_flags:
    intention_demande_identifiants: true
    is_prospect: true

"PROSPECT_UBER_20:DEMANDE_AUTRES_DATES":
  template: "response_master.html"
  description: "Prospect demande dates"
  context_flags:
    intention_demande_date: true
    is_prospect: true
    show_dates_section: true
```

### 3.8 CONVOCATION_RECEIVED × RESULTAT_EXAMEN

```yaml
"CONVOCATION_RECEIVED:RESULTAT_EXAMEN":
  template: "response_master.html"
  description: "A la convocation, demande résultat - examen pas encore passé"
  context_flags:
    intention_resultat_examen: true
    evalbox_convoc_recue: true
    examen_pas_encore_passe: true
```

### 3.9 Wildcard pour nouvelles intentions

```yaml
"*:PERMIS_PROBATOIRE":
  template: "response_master.html"
  context_flags:
    intention_permis_probatoire: true

"*:DATE_LOINTAINE_EXAMT3P":
  template: "response_master.html"
  context_flags:
    intention_date_lointaine: true
    show_dates_section: true
```

---

## Phase 4 : Nouveaux Partials (4 seulement)

### 4.1 `partials/prospect/rappel_inscription.html` (NOUVEAU)

**Créer le répertoire** : `states/templates/partials/prospect/`

```html
<!-- Partial: Rappel inscription pour prospects -->
<br>
<b style="color: #d35400;">Rappel : Finalisez votre inscription</b><br>
Votre inscription n'est pas encore finalisée. Pour bénéficier de l'offre Uber à 20€ et accéder à tous nos services, veuillez compléter votre paiement sur <a href="https://cab-formations.fr/uberxcab_welcome">notre page d'inscription</a>.<br>
<br>
Une fois le paiement effectué, vous recevrez :<br>
→ Vos accès à la formation e-learning<br>
→ La création de votre compte ExamT3P pour l'inscription à l'examen<br>
<br>
```

### 4.2 `partials/report/deja_effectue.html` (NOUVEAU)

```html
<!-- Partial: Report déjà effectué automatiquement -->
<b>Concernant votre demande de report</b><br>
Votre dossier ayant été refusé par la CMA, votre inscription a été <b>automatiquement reportée</b> sur la prochaine session d'examen.<br>
<br>
{{#if has_pieces_refusees}}
<b>Documents à corriger :</b><br>
{{#each pieces_refusees_details}}
• <b>{{this.nom}}</b> - {{this.motif}}<br>
  → {{this.solution}}<br>
{{/each}}
<br>
{{/if}}
{{#if has_next_dates}}
<b>Prochaine date d'examen :</b><br>
{{#each next_dates}}
{{#if this.is_first_of_dept}}
→ {{this.date_examen_formatted}} - Département {{this.Departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/if}}
{{/each}}
<br>
{{/if}}
<b style="color: #c0392b;">Important :</b> Corrigez vos documents avant la date de clôture pour éviter un nouveau report.<br>
<br>
```

### 4.3 `partials/intentions/permis_probatoire.html` (NOUVEAU)

```html
<!-- Partial: Réponse intention PERMIS_PROBATOIRE -->
<b>Concernant votre permis probatoire</b><br>
Pour passer l'examen VTC, vous devez avoir terminé votre période de probation de permis de conduire (3 ans, ou 2 ans si conduite accompagnée).<br>
<br>
<b>Règle importante :</b><br>
Vous pouvez vous inscrire à un examen dont la <b>date de clôture des inscriptions</b> est postérieure à la fin de votre période probatoire.<br>
<br>
{{#if has_next_dates}}
<b>Prochaines dates d'examen disponibles :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.Departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/each}}
<br>
{{/if}}
<b>Merci de nous préciser la date de fin de votre période probatoire</b> (indiquée sur votre permis de conduire) afin que nous puissions vous confirmer les dates d'examen accessibles pour vous.<br>
<br>
```

### 4.4 `partials/intentions/date_lointaine.html` (NOUVEAU)

```html
<!-- Partial: Réponse intention DATE_LOINTAINE_EXAMT3P -->
<b>Concernant les dates d'examen futures</b><br>
La plateforme ExamT3P n'affiche que les <b>2 prochaines dates d'examen</b> par département. Les dates ultérieures ne sont pas encore visibles.<br>
<br>
<b>Voici comment procéder :</b><br>
1. Inscrivez-vous sur la date la plus lointaine actuellement disponible<br>
2. Une fois inscrit, envoyez un message via l'onglet <b>Messagerie</b> de <a href="https://www.exament3p.fr">exament3p.fr</a><br>
3. Précisez la date à laquelle vous souhaitez être positionné<br>
<br>
La CMA vous repositionnera sur la date souhaitée dès qu'elle sera ouverte aux inscriptions.<br>
<br>
{{#if has_next_dates}}
<b>Dates actuellement disponibles :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.Departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/each}}
<br>
{{/if}}
```

### 4.5 Partials NON créés (existent déjà)

| Partial proposé | Utiliser à la place |
|-----------------|---------------------|
| `intentions/changement_departement.html` | `intentions/autres_departements.html` |
| `intentions/changement_session.html` | `intentions/confirmation_session.html` |

---

## Phase 5 : Modification des Partials Existants

### 5.1 Modifier `partials/intentions/demande_convocation.html`

**Remplacer le contenu actuel par :**

```html
<!-- Partial: Réponse à l'intention DEMANDE_CONVOCATION -->
<b>Concernant votre convocation</b><br>
<br>
{{#if evalbox_convoc_recue}}
Votre convocation est disponible ! Vous pouvez la télécharger sur <a href="https://www.exament3p.fr">exament3p.fr</a> avec vos identifiants.<br>
{{#if identifiant_examt3p}}
→ Identifiant : <b>{{identifiant_examt3p}}</b><br>
→ Mot de passe : <b>{{mot_de_passe_examt3p}}</b><br>
{{/if}}
<br>
<i>Pensez à l'imprimer pour le jour de l'examen.</i><br>
{{/if}}

{{#if evalbox_refus_cma}}
Votre dossier a été <b>refusé par la CMA</b>. Vous ne pouvez pas recevoir de convocation tant que les documents suivants n'auront pas été corrigés :<br>
<br>
{{#if has_pieces_refusees}}
{{#each pieces_refusees_details}}
<b>{{this.nom}}</b><br>
→ Motif : {{this.motif}}<br>
→ Solution : {{this.solution}}<br>
<br>
{{/each}}
{{/if}}
{{#if cloture_passed}}
<b style="color: #c0392b;">Report automatique</b><br>
La date de clôture étant passée, votre inscription a été automatiquement reportée sur la prochaine session.<br>
{{else}}
<b style="color: #d35400;">Action urgente requise</b><br>
Corrigez vos documents AVANT le {{date_cloture}} pour conserver votre date d'examen du {{date_examen}}.<br>
{{/if}}
<br>
<b>Comment corriger :</b><br>
→ Connectez-vous sur <a href="https://www.exament3p.fr">exament3p.fr</a><br>
{{#if identifiant_examt3p}}
→ Identifiant : <b>{{identifiant_examt3p}}</b><br>
→ Mot de passe : <b>{{mot_de_passe_examt3p}}</b><br>
{{/if}}
{{/if}}

{{#if evalbox_dossier_synchronise}}
Votre dossier est actuellement <b>en cours d'instruction</b> par la CMA. La convocation sera disponible une fois votre dossier validé, environ 7 jours avant l'examen.<br>
<br>
{{#if exam_within_7_days}}
<b style="color: #c0392b;">Attention :</b> Votre examen est prévu dans moins de 7 jours et votre dossier n'est toujours pas validé. Il sera probablement reporté sur la prochaine session.<br>
<br>
<b>Action recommandée :</b><br>
Envoyez un message via l'onglet <b>Messagerie</b> de <a href="https://www.exament3p.fr">exament3p.fr</a> pour demander le traitement urgent de votre dossier.<br>
{{else}}
<b>En attendant :</b><br>
→ Surveillez vos emails (et spams) quotidiennement<br>
→ Si la CMA refuse des documents, corrigez-les rapidement avant la date de clôture<br>
{{/if}}
{{/if}}

{{#if deadline_missed}}
La date de clôture des inscriptions pour votre examen du {{date_examen}} est passée, et votre dossier n'était pas validé à temps.<br>
<br>
<b>Votre inscription a été automatiquement reportée</b> sur la prochaine session d'examen.<br>
<br>
{{#if has_next_dates}}
{{#each next_dates}}
{{#if this.is_first_of_dept}}
<b>Prochaine date :</b> {{this.date_examen_formatted}} (clôture : {{this.date_cloture_formatted}})<br>
{{/if}}
{{/each}}
{{/if}}
<br>
Surveillez vos emails pour la validation de votre dossier et l'envoi de votre convocation.<br>
{{/if}}

{{#if date_examen_vide}}
Vous n'avez pas encore de date d'examen assignée. Pour recevoir une convocation, vous devez d'abord choisir une date d'examen.<br>
<br>
{{#if has_next_dates}}
<b>Prochaines dates disponibles :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.Departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/each}}
<br>
{{/if}}
Merci de nous indiquer la date qui vous convient pour que nous puissions finaliser votre inscription.<br>
{{/if}}

{{#if evalbox_valide_cma}}
{{#unless evalbox_convoc_recue}}
{{#if convocation_anormale}}
<b style="color: #c0392b;">Situation anormale</b><br>
Votre dossier est validé et votre examen approche, mais vous n'avez pas encore reçu votre convocation. Ce n'est pas normal.<br>
<br>
<b>Actions urgentes à effectuer :</b><br>
1. <b>Vérifiez vos spams</b> - la convocation peut s'y trouver<br>
2. <b>Connectez-vous sur <a href="https://www.exament3p.fr">exament3p.fr</a></b> pour vérifier si elle est disponible dans votre espace<br>
3. <b>Envoyez un message via l'onglet Messagerie</b> de la plateforme pour contacter la CMA<br>
4. Si aucune réponse sous 24h, <b>contactez directement la CMA</b> de votre département<br>
<br>
{{#if identifiant_examt3p}}
Vos identifiants ExamT3P :<br>
→ Identifiant : <b>{{identifiant_examt3p}}</b><br>
→ Mot de passe : <b>{{mot_de_passe_examt3p}}</b><br>
{{/if}}
{{else}}
Votre dossier est validé par la CMA. Votre convocation vous sera envoyée par email environ 7 à 10 jours avant votre examen du {{date_examen}}.<br>
<br>
{{#if date_convocation}}
→ Attendue aux alentours du <b>{{date_convocation}}</b><br>
{{/if}}
<br>
Pensez à vérifier vos spams. La convocation sera également disponible sur votre espace <a href="https://www.exament3p.fr">exament3p.fr</a>.<br>
{{/if}}
{{/unless}}
{{/if}}
<br>
```

### 5.2 Modifier `partials/intentions/resultat_examen.html`

**Remplacer le contenu actuel par :**

```html
<!-- Partial: Réponse à l'intention RESULTAT_EXAMEN -->
<b>Concernant votre résultat d'examen</b><br>
<br>
{{#if resultat_admis}}
{{> partials/resultats/admis}}
{{/if}}

{{#if resultat_non_admis}}
{{> partials/resultats/non_admis}}
{{/if}}

{{#if resultat_absent}}
{{> partials/resultats/absent}}
{{/if}}

{{#if examen_pas_encore_passe}}
Votre examen est prévu le <b>{{date_examen}}</b>. Les résultats ne seront disponibles qu'après avoir passé l'examen.<br>
<br>
Vous recevrez vos résultats par email dans les 48 à 72 heures suivant l'examen. Ils seront également consultables sur votre espace <a href="https://www.exament3p.fr">exament3p.fr</a>.<br>
<br>
En attendant, n'hésitez pas à réviser sur votre <a href="https://cab-formations.fr/user">espace e-learning</a>.<br>
{{/if}}

{{#unless resultat_admis}}
{{#unless resultat_non_admis}}
{{#unless resultat_absent}}
{{#unless examen_pas_encore_passe}}
Les résultats sont généralement disponibles sous 48 à 72 heures après l'examen.<br>
Vous recevrez une notification par email dès que votre résultat sera publié. Vous pourrez également le consulter sur <a href="https://www.exament3p.fr">exament3p.fr</a>.<br>
{{/unless}}
{{/unless}}
{{/unless}}
{{/unless}}
<br>
```

---

## Phase 6 : Modification de `response_master.html`

### 6.1 Ajouter la section PROSPECT

Après les sections d'intention existantes, ajouter :

```html
<!-- SECTION PROSPECT : Rappel inscription -->
{{#if is_prospect}}
{{> partials/prospect/rappel_inscription}}
{{/if}}
```

### 6.2 Ajouter les nouvelles intentions

Dans la section des intentions :

```html
{{#if intention_permis_probatoire}}
{{> partials/intentions/permis_probatoire}}
{{/if}}

{{#if intention_date_lointaine}}
{{> partials/intentions/date_lointaine}}
{{/if}}
```

---

## Phase 7 : Ajouter le flag `is_prospect` dans le contexte

### 7.1 Dans `state_detector.py`

Le flag `is_uber_prospect` existe déjà. Ajouter un alias :

```python
'is_prospect': is_uber_prospect,
```

### 7.2 Dans `template_engine.py`

Propager dans `_prepare_placeholder_data()` :

```python
'is_prospect': context.get('is_prospect', False) or context.get('is_uber_prospect', False),
```

---

## Checklist d'Implémentation

### Phase 1 : Variables et Flags
- [ ] Ajouter `exam_within_7_days`, `exam_within_10_days`, `examen_pas_encore_passe`, `examen_imminent`, `convocation_anormale` dans `state_detector.py`
- [ ] Ajouter `pieces_refusees_details`, `has_pieces_refusees` dans `state_detector.py`
- [ ] Propager tous les nouveaux flags dans `template_engine.py`

### Phase 2 : Intentions
- [ ] Ajouter `PERMIS_PROBATOIRE` (I38) dans `state_intention_matrix.yaml`
- [ ] Ajouter `DATE_LOINTAINE_EXAMT3P` (I39) dans `state_intention_matrix.yaml`

### Phase 3 : Entrées Matrice
- [ ] Ajouter les 10 entrées État×Intention listées ci-dessus
- [ ] Ajouter les 2 wildcards pour nouvelles intentions

### Phase 4 : Nouveaux Partials
- [ ] Créer répertoire `states/templates/partials/prospect/`
- [ ] Créer `partials/prospect/rappel_inscription.html`
- [ ] Créer `partials/report/deja_effectue.html`
- [ ] Créer `partials/intentions/permis_probatoire.html`
- [ ] Créer `partials/intentions/date_lointaine.html`

### Phase 5 : Modification Partials
- [ ] Modifier `partials/intentions/demande_convocation.html`
- [ ] Modifier `partials/intentions/resultat_examen.html`

### Phase 6 : Modification response_master.html
- [ ] Ajouter section PROSPECT
- [ ] Ajouter sections nouvelles intentions

### Phase 7 : Flag is_prospect
- [ ] Ajouter alias `is_prospect` dans `state_detector.py`
- [ ] Propager dans `template_engine.py`

---

## Tests de Validation

| # | Scénario | État | Intention | Résultat attendu |
|---|----------|------|-----------|------------------|
| T1 | Refus CMA + convocation | Evalbox="Refusé CMA" | DEMANDE_CONVOCATION | Liste docs refusés + action corriger |
| T2 | Refus CMA + report | Evalbox="Refusé CMA" | REPORT_DATE | Report auto expliqué |
| T3 | Dossier sync J-5 + convocation | Evalbox="Dossier Synchronisé" + exam_within_7_days | DEMANDE_CONVOCATION | Alerte report probable |
| T4 | Pas de date + convocation | Date_examen=null | DEMANDE_CONVOCATION | Proposer dates d'abord |
| T5 | VALIDE CMA J-5 + convocation | convocation_anormale=true | DEMANDE_CONVOCATION | Alerte anormale + actions urgentes |
| T6 | Prospect + statut | is_prospect=true | STATUT_DOSSIER | Réponse + rappel inscription |
| T7 | Convoc reçue + résultat | Evalbox="Convoc CMA reçue" | RESULTAT_EXAMEN | Examen pas encore passé |
| T8 | Permis probatoire | Any | PERMIS_PROBATOIRE | Explication règle + dates |
| T9 | Date lointaine | Any | DATE_LOINTAINE_EXAMT3P | Procédure inscription + message CMA |

---

## Fichiers Modifiés (Résumé Final)

| Fichier | Action |
|---------|--------|
| `src/state_engine/state_detector.py` | Ajouter 8 nouveaux flags |
| `src/state_engine/template_engine.py` | Propager 8 nouveaux flags |
| `states/state_intention_matrix.yaml` | Ajouter 2 intentions + 12 entrées matrice |
| `states/templates/partials/prospect/rappel_inscription.html` | Créer |
| `states/templates/partials/report/deja_effectue.html` | Créer |
| `states/templates/partials/intentions/permis_probatoire.html` | Créer |
| `states/templates/partials/intentions/date_lointaine.html` | Créer |
| `states/templates/partials/intentions/demande_convocation.html` | Modifier (enrichir) |
| `states/templates/partials/intentions/resultat_examen.html` | Modifier (enrichir) |
| `states/templates/response_master.html` | Ajouter sections |

**Total : 10 fichiers, dont 4 créations et 6 modifications**
