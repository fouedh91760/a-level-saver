# Instructions d'Implémentation - Scénarios Manquants

**Date** : 2026-01-29
**Objectif** : Corriger les combinaisons État × Intention non gérées dans le State Engine

---

## Table des Matières

1. [Contexte et Architecture](#1-contexte-et-architecture)
2. [Règles Métier à Respecter](#2-règles-métier-à-respecter)
3. [Combinaisons État × Intention à Ajouter](#3-combinaisons-état--intention-à-ajouter)
4. [Nouvelles Intentions à Créer](#4-nouvelles-intentions-à-créer)
5. [Templates et Partials à Créer](#5-templates-et-partials-à-créer)
6. [Harmonisation des Noms d'États](#6-harmonisation-des-noms-détats)
7. [Ordre d'Implémentation](#7-ordre-dimplémentation)
8. [Tests de Validation](#8-tests-de-validation)

---

## 1. Contexte et Architecture

### Fichiers Sources de Vérité

| Fichier | Contenu |
|---------|---------|
| `states/candidate_states.yaml` | Définition des 38 états (SOURCE DE VÉRITÉ) |
| `states/state_intention_matrix.yaml` | Définition des intentions + matrice État×Intention |
| `states/templates/partials/` | Templates modulaires par catégorie |
| `src/state_engine/state_detector.py` | Détection des états |
| `src/state_engine/template_engine.py` | Génération des réponses |

### Processus Standard (voir CLAUDE.md)

1. Ajouter l'entrée dans `state_intention_matrix.yaml` section `matrix:`
2. Créer le partial HTML si nécessaire dans `states/templates/partials/`
3. Propager les flags dans `template_engine.py` si nouveau flag
4. Tester sur un ticket réel

---

## 2. Règles Métier à Respecter

### 2.1 Règles CMA / Clôture

| Situation | Conséquence |
|-----------|-------------|
| Refus CMA AVANT clôture | Candidat doit corriger AVANT clôture, sinon report auto |
| Refus CMA APRÈS clôture | Report automatique sur prochaine date |
| Dossier Synchronisé à J-7 | Report CERTAIN sur prochaine date |
| Validation AVANT clôture | Convoqué sur la date prévue |
| Validation APRÈS clôture | Convoqué sur date ExamT3P (peut différer de Zoho) |

### 2.2 Convocation

- **Timing normal** : J-7 avant examen
- **Si VALIDE à J-7 sans convoc** : ANORMAL → contacter CMA urgemment + vérifier spams
- **Statut convocation** : "En attente de convocation" (ExamT3P) = "Convoc CMA reçue" (Zoho)

### 2.3 Report de Date

| Situation | Possible ? |
|-----------|------------|
| Avant clôture | ✅ Oui |
| Après clôture + force majeure | ✅ Oui (avec justificatif) |
| Après clôture sans force majeure | ❌ Non → réinscription à ses frais (241€) |
| Après convocation + force majeure | ✅ Oui |
| Après convocation sans force majeure | ❌ Non → réinscription à ses frais |

### 2.4 Documents Refusés

- **Toujours détailler** : nom du document + motif de refus + solution
- Utiliser `examt3p_data['pieces_refusees_details']` qui contient :
  ```python
  {
      'nom': "Justificatif de domicile",
      'motif': "Document de plus de 6 mois",
      'solution': "Fournir un justificatif de moins de 6 mois"
  }
  ```

### 2.5 Changement de Département

| Timing | Possible ? |
|--------|------------|
| Avant création compte ExamT3P | ✅ Facile - choisir n'importe quel département |
| Après création compte | ⚠️ Demande CMA requise, risque de retard |
| Après clôture | ❌ Impossible |

### 2.6 Permis Probatoire

- **Règle** : Inscription uniquement si `date_cloture_examen > fin_probation_permis`
- **Info non disponible dans CRM** → détecter via message candidat
- Si date fournie → proposer date d'examen appropriée
- Si date non fournie → expliquer règle + demander la date

### 2.7 Dates ExamT3P

- Seules les **2 prochaines dates** par département sont visibles sur ExamT3P
- Si candidat veut date plus lointaine → s'inscrire sur la plus lointaine visible + message via Messagerie ExamT3P

### 2.8 Multi-Intentions

- **Toujours répondre aux 2 intentions** dans la même réponse
- Utiliser `primary_intent` + `secondary_intents` du TriageAgent

### 2.9 PROSPECT

- **Ne PAS bloquer** les prospects qui posent des questions
- Répondre à leur question + rappeler de finaliser l'inscription (paiement 20€)

---

## 3. Combinaisons État × Intention à Ajouter

### 3.1 REFUSED_CMA × DEMANDE_CONVOCATION

**Fichier** : `states/state_intention_matrix.yaml`

```yaml
# Dans section matrix:
"EVALBOX_REFUSE_CMA:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation mais dossier refusé CMA"
  context_flags:
    intention_demande_convocation: true
    evalbox_refus_cma: true
    show_documents_refuses: true
    show_statut_section: true
```

**Partial à créer** : `states/templates/partials/intentions/demande_convocation.html`

Modifier pour ajouter la gestion du cas `evalbox_refus_cma` :

```html
{{#if evalbox_refus_cma}}
<b>Concernant votre convocation</b><br>
Votre dossier a été refusé par la CMA. Vous ne pouvez pas recevoir de convocation tant que les documents suivants n'auront pas été corrigés :<br>
<br>
{{#each pieces_refusees_details}}
<b>{{this.nom}}</b><br>
→ Motif : {{this.motif}}<br>
→ Solution : {{this.solution}}<br>
<br>
{{/each}}
{{#if cloture_passed}}
<b style="color: #c0392b;">Report automatique</b><br>
La date de clôture étant passée, votre inscription a été automatiquement reportée sur la prochaine session d'examen.<br>
<br>
{{#if next_dates}}
<b>Prochaine date disponible :</b><br>
{{#each next_dates}}
{{#if @first}}
→ Examen du {{this.date_examen_formatted}} (clôture : {{this.date_cloture_formatted}})<br>
{{/if}}
{{/each}}
<br>
{{/if}}
{{else}}
<b style="color: #d35400;">Action urgente requise</b><br>
Corrigez vos documents AVANT le {{date_cloture_formatted}} pour conserver votre date d'examen du {{date_examen_formatted}}.<br>
<br>
{{/if}}
<b>Comment corriger :</b><br>
→ Connectez-vous sur <a href="https://www.exament3p.fr">exament3p.fr</a><br>
{{#if identifiant_examt3p}}
→ Identifiant : <b>{{identifiant_examt3p}}</b><br>
→ Mot de passe : <b>{{mot_de_passe_examt3p}}</b><br>
{{/if}}
<br>
{{/if}}
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

**Partial à créer/modifier** : `states/templates/partials/report/deja_effectue.html`

```html
<b>Concernant votre demande de report</b><br>
Votre dossier ayant été refusé par la CMA, votre inscription a été <b>automatiquement reportée</b> sur la prochaine session d'examen.<br>
<br>
<b>Documents à corriger :</b><br>
{{#each pieces_refusees_details}}
• <b>{{this.nom}}</b> - {{this.motif}}<br>
  → {{this.solution}}<br>
{{/each}}
<br>
{{#if next_dates}}
<b>Prochaine date d'examen :</b> {{next_dates.0.date_examen_formatted}}<br>
<b>Date limite de correction :</b> {{next_dates.0.date_cloture_formatted}}<br>
<br>
{{/if}}
<b style="color: #c0392b;">Important :</b> Corrigez vos documents avant cette date limite pour éviter un nouveau report.<br>
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

**Contenu du partial** (ajouter dans `demande_convocation.html`) :

```html
{{#if evalbox_dossier_synchronise}}
<b>Concernant votre convocation</b><br>
Votre dossier est actuellement <b>en cours d'instruction</b> par la CMA. La convocation sera disponible une fois votre dossier validé, environ 7 jours avant l'examen.<br>
<br>
{{#if days_until_exam}}
{{#if (lte days_until_exam 7)}}
<b style="color: #c0392b;">Attention :</b> Votre examen est prévu dans {{days_until_exam}} jours et votre dossier n'est toujours pas validé. Il sera probablement reporté sur la prochaine session.<br>
<br>
<b>Action recommandée :</b><br>
Envoyez un message via l'onglet <b>Messagerie</b> de la plateforme <a href="https://www.exament3p.fr">exament3p.fr</a> pour demander le traitement de votre dossier avant la prochaine date de clôture.<br>
<br>
{{/if}}
{{/if}}
<b>En attendant :</b><br>
→ Surveillez vos emails (et spams) quotidiennement<br>
→ Si la CMA refuse des documents, corrigez-les rapidement avant la date de clôture<br>
{{/if}}
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

**Contenu** (ajouter dans `demande_convocation.html`) :

```html
{{#if deadline_missed}}
<b>Concernant votre convocation</b><br>
La date de clôture des inscriptions pour votre examen du {{date_examen_formatted}} est passée, et votre dossier n'était pas validé à temps.<br>
<br>
<b>Votre inscription a été automatiquement reportée</b> sur la prochaine session d'examen.<br>
<br>
{{#if next_dates}}
<b>Prochaine date d'examen :</b> {{next_dates.0.date_examen_formatted}}<br>
<b>Nouvelle date de clôture :</b> {{next_dates.0.date_cloture_formatted}}<br>
{{/if}}
<br>
Surveillez vos emails pour la validation de votre dossier et l'envoi de votre convocation.<br>
{{/if}}
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

**Contenu** :

```html
{{#if date_examen_vide}}
<b>Concernant votre convocation</b><br>
Vous n'avez pas encore de date d'examen assignée. Pour recevoir une convocation, vous devez d'abord choisir une date d'examen.<br>
<br>
<b>Prochaines dates disponibles :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/each}}
<br>
Merci de nous indiquer la date qui vous convient pour que nous puissions finaliser votre inscription.<br>
{{/if}}
```

### 3.6 VALIDE_CMA × DEMANDE_CONVOCATION (J-7 sans convoc)

```yaml
"DATE_FUTURE_VALIDE_CMA:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Demande convocation - validé CMA"
  context_flags:
    intention_demande_convocation: true
    evalbox_valide_cma: true
    show_statut_section: true
```

**Modifier le partial** pour gérer le cas J-7 :

```html
{{#if evalbox_valide_cma}}
<b>Concernant votre convocation</b><br>
{{#if (lte days_until_exam 7)}}
{{#if (not evalbox_convoc_recue)}}
<b style="color: #c0392b;">Situation anormale</b><br>
Votre dossier est validé et votre examen est dans {{days_until_exam}} jours, mais vous n'avez pas encore reçu votre convocation. Ce n'est pas normal.<br>
<br>
<b>Actions urgentes à effectuer :</b><br>
1. <b>Vérifiez vos spams</b> - la convocation peut s'y trouver<br>
2. <b>Connectez-vous sur <a href="https://www.exament3p.fr">exament3p.fr</a></b> pour vérifier si la convocation est disponible dans votre espace<br>
3. <b>Envoyez un message via l'onglet Messagerie</b> de la plateforme pour contacter la CMA<br>
4. Si aucune réponse, <b>contactez directement la CMA</b> de votre département (voire déplacez-vous si possible)<br>
<br>
{{#if identifiant_examt3p}}
Vos identifiants ExamT3P :<br>
→ Identifiant : <b>{{identifiant_examt3p}}</b><br>
→ Mot de passe : <b>{{mot_de_passe_examt3p}}</b><br>
{{/if}}
{{/if}}
{{else}}
Votre dossier est validé par la CMA. Votre convocation vous sera envoyée par email environ 7 jours avant votre examen du {{date_examen_formatted}}.<br>
<br>
Pensez à vérifier vos spams. La convocation sera également disponible sur votre espace <a href="https://www.exament3p.fr">exament3p.fr</a>.<br>
{{/if}}
{{/if}}
```

### 3.7 DOSSIER_SYNCHRONIZED à J-7 (report certain)

Ce cas est déjà couvert par 3.3, mais il faut s'assurer que le flag `days_until_exam <= 7` est bien géré.

### 3.8 UBER_PROSPECT × Intentions diverses

```yaml
# Pour chaque intention, ajouter une entrée PROSPECT
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

**Partial à créer** : `states/templates/partials/prospect/rappel_inscription.html`

```html
<b style="color: #d35400;">Rappel : Finalisez votre inscription</b><br>
Votre inscription n'est pas encore finalisée. Pour bénéficier de l'offre Uber et accéder à tous les services, veuillez compléter votre paiement sur <a href="https://cab-formations.fr/uberxcab_welcome">notre page d'inscription</a>.<br>
```

Ajouter dans `response_master.html` après la section intention :

```html
{{#if is_prospect}}
<br>
{{> partials/prospect/rappel_inscription}}
<br>
{{/if}}
```

### 3.9 CONVOCATION_RECEIVED × RESULTAT_EXAMEN

```yaml
"CONVOCATION_RECEIVED:RESULTAT_EXAMEN":
  template: "response_master.html"
  description: "A la convocation, demande résultat - examen pas encore passé"
  context_flags:
    intention_resultat_examen: true
    evalbox_convoc_recue: true
    examen_pas_encore_passe: true
```

**Partial** (modifier `partials/intentions/resultat_examen.html`) :

```html
{{#if examen_pas_encore_passe}}
<b>Concernant vos résultats</b><br>
Votre examen est prévu le <b>{{date_examen_formatted}}</b>. Les résultats ne seront disponibles qu'après avoir passé l'examen.<br>
<br>
Vous recevrez vos résultats par email dans les jours suivant l'examen. Ils seront également consultables sur votre espace <a href="https://www.exament3p.fr">exament3p.fr</a>.<br>
<br>
En attendant, n'hésitez pas à réviser sur votre <a href="https://cab-formations.fr/user">espace e-learning</a>.<br>
{{/if}}
```

### 3.10 EXAM_DATE_PAST_VALIDATED × DEMANDE_CONVOCATION

```yaml
"EXAM_DATE_PAST_VALIDATED:DEMANDE_CONVOCATION":
  template: "response_master.html"
  description: "Date passée + validé, demande convocation"
  context_flags:
    intention_demande_convocation: true
    examen_probablement_passe: true
```

**Contenu** :

```html
{{#if examen_probablement_passe}}
<b>Concernant votre convocation</b><br>
Votre examen du {{date_examen_formatted}} est passé. Avez-vous pu vous présenter à l'examen ?<br>
<br>
<b>Si vous avez passé l'examen :</b><br>
Les résultats seront disponibles dans les jours suivants sur votre espace <a href="https://www.exament3p.fr">exament3p.fr</a> et par email.<br>
<br>
<b>Si vous n'avez pas pu vous présenter :</b><br>
→ Avec un justificatif de force majeure (certificat médical, etc.) : un report est possible<br>
→ Sans justificatif : une nouvelle inscription avec paiement des frais d'examen (241€) sera nécessaire<br>
{{/if}}
```

---

## 4. Nouvelles Intentions à Créer

### 4.1 DEMANDE_FACTURE_ATTESTATION (I38)

**Fichier** : `states/state_intention_matrix.yaml` section `intentions:`

```yaml
DEMANDE_FACTURE_ATTESTATION:
  id: "I38"
  description: "Demande de facture ou attestation"
  triggers:
    - "facture"
    - "attestation"
    - "reçu"
    - "justificatif de paiement"
    - "attestation de formation"
    - "certificat"
  routing: "Backoffice"
  priority: 85
```

### 4.2 PERMIS_PROBATOIRE (I39)

```yaml
PERMIS_PROBATOIRE:
  id: "I39"
  description: "Question sur permis probatoire"
  triggers:
    - "permis probatoire"
    - "jeune permis"
    - "3 ans de permis"
    - "fin de probation"
    - "permis de moins de 3 ans"
  priority: 80
```

**Partial à créer** : `states/templates/partials/intentions/permis_probatoire.html`

```html
<b>Concernant votre permis probatoire</b><br>
Pour passer l'examen VTC, vous devez avoir terminé votre période de probation de permis de conduire.<br>
<br>
<b>Règle :</b> Vous ne pouvez vous inscrire qu'à un examen dont la date de clôture des inscriptions est APRÈS la fin de votre période probatoire.<br>
<br>
{{#if date_fin_probation}}
Selon la date de fin de probation que vous nous avez indiquée ({{date_fin_probation}}), voici les dates d'examen possibles :<br>
{{#each next_dates_after_probation}}
→ {{this.date_examen_formatted}} - Département {{this.departement}}<br>
{{/each}}
{{else}}
<b>Merci de nous préciser la date de fin de votre période probatoire</b> (indiquée sur votre permis de conduire) afin que nous puissions vous indiquer les dates d'examen disponibles pour vous.<br>
{{/if}}
```

### 4.3 CHANGEMENT_DEPARTEMENT (I40)

```yaml
CHANGEMENT_DEPARTEMENT:
  id: "I40"
  description: "Demande de changement de département"
  triggers:
    - "changer de département"
    - "autre département"
    - "autre CMA"
    - "m'inscrire ailleurs"
    - "changer de région"
  priority: 75
```

**Partial** : `states/templates/partials/intentions/changement_departement.html`

```html
<b>Concernant le changement de département</b><br>
{{#if compte_existe}}
{{#if cloture_passed}}
<b style="color: #c0392b;">Changement impossible</b><br>
La date de clôture étant passée, il n'est plus possible de changer de département pour cette session. Vous pouvez demander un changement pour la prochaine session.<br>
{{else}}
Un changement de département est possible mais nécessite une demande auprès de la CMA.<br>
<br>
<b>Attention :</b> Cette procédure peut retarder votre inscription. Si la validation arrive après la date de clôture, vous serez reporté sur la session suivante.<br>
<br>
<b>Pour effectuer la demande :</b><br>
Envoyez un message via l'onglet <b>Messagerie</b> de <a href="https://www.exament3p.fr">exament3p.fr</a> en précisant le département souhaité.<br>
{{/if}}
{{else}}
<b>Bonne nouvelle !</b> Vous n'avez pas encore de compte ExamT3P, vous pouvez donc choisir librement votre département d'inscription.<br>
<br>
<b>Dates disponibles par département :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.departement}} (clôture : {{this.date_cloture_formatted}})<br>
{{/each}}
<br>
Indiquez-nous le département et la date qui vous conviennent.<br>
{{/if}}
```

### 4.4 CHANGEMENT_SESSION (I41)

```yaml
CHANGEMENT_SESSION:
  id: "I41"
  description: "Changement de session jour/soir"
  triggers:
    - "changer de session"
    - "passer en cours du jour"
    - "passer en cours du soir"
    - "changer pour le jour"
    - "changer pour le soir"
  crm_update: true
  update_fields:
    - Session_choisie
    - Preference_horaire
  priority: 70
```

**Partial** : `states/templates/partials/intentions/changement_session.html`

```html
<b>Concernant votre changement de session</b><br>
Pas de problème, nous pouvons modifier votre session de formation.<br>
<br>
{{#if date_examen}}
<b>Sessions disponibles avant votre examen du {{date_examen_formatted}} :</b><br>
{{#each sessions_proposees}}
{{#if this.is_before_exam}}
→ <b>{{this.nom}}</b> ({{this.type}}) : du {{this.debut}} au {{this.fin}}<br>
{{/if}}
{{/each}}
<br>
Merci de nous confirmer la session qui vous convient et nous mettrons à jour votre inscription.<br>
{{else}}
Veuillez d'abord choisir une date d'examen, puis nous pourrons vous proposer les sessions de formation correspondantes.<br>
{{/if}}
```

### 4.5 DATE_NON_DISPONIBLE_EXAMT3P (I42)

```yaml
DATE_NON_DISPONIBLE_EXAMT3P:
  id: "I42"
  description: "Veut une date pas encore visible sur ExamT3P"
  triggers:
    - "date pas disponible"
    - "date non visible"
    - "date pas encore"
    - "date de septembre"
    - "date de octobre"
    - "date de novembre"
    - "date de décembre"
    - "plus tard dans l'année"
  priority: 70
```

**Partial** : `states/templates/partials/intentions/date_non_disponible.html`

```html
<b>Concernant les dates d'examen futures</b><br>
La plateforme ExamT3P n'affiche que les 2 prochaines dates d'examen par département. Les dates ultérieures ne sont pas encore visibles.<br>
<br>
<b>Voici comment procéder :</b><br>
1. Inscrivez-vous sur la date la plus lointaine actuellement disponible<br>
2. Envoyez ensuite un message via l'onglet <b>Messagerie</b> de <a href="https://www.exament3p.fr">exament3p.fr</a><br>
3. Précisez la date à laquelle vous souhaitez être positionné<br>
<br>
La CMA vous repositionnera sur la date souhaitée dès qu'elle sera ouverte aux inscriptions.<br>
<br>
<b>Dates actuellement disponibles :</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} - Département {{this.departement}}<br>
{{/each}}
```

---

## 5. Templates et Partials à Créer

### 5.1 Nouveaux Partials

| Chemin | Description |
|--------|-------------|
| `partials/prospect/rappel_inscription.html` | Rappel pour finaliser inscription prospect |
| `partials/report/deja_effectue.html` | Report déjà fait automatiquement (refus CMA) |
| `partials/intentions/permis_probatoire.html` | Gestion permis probatoire |
| `partials/intentions/changement_departement.html` | Changement de département |
| `partials/intentions/changement_session.html` | Changement session jour/soir |
| `partials/intentions/date_non_disponible.html` | Date pas encore visible ExamT3P |

### 5.2 Partials à Modifier

| Chemin | Modifications |
|--------|---------------|
| `partials/intentions/demande_convocation.html` | Ajouter cas refus_cma, dossier_synchronise, deadline_missed, date_vide, valide_j7 |
| `partials/intentions/resultat_examen.html` | Ajouter cas examen_pas_encore_passe |
| `partials/actions/corriger_documents.html` | Enrichir avec motifs et solutions |

### 5.3 Modification response_master.html

Ajouter la section prospect :

```html
<!-- Après les sections d'intention -->
{{#if is_prospect}}
<br>
{{> partials/prospect/rappel_inscription}}
{{/if}}
```

---

## 6. Harmonisation des Noms d'États

### Problème Identifié

La matrice utilise des noms différents de `candidate_states.yaml` :

| candidate_states.yaml | state_intention_matrix.yaml (actuel) | Action |
|----------------------|-------------------------------------|--------|
| REFUSED_CMA | EVALBOX_REFUSE_CMA | Garder les deux (alias) |
| VALIDE_CMA_WAITING_CONVOC | DATE_FUTURE_VALIDE_CMA | Garder les deux |
| DEADLINE_MISSED | DEADLINE_RATEE | Garder les deux |
| CREDENTIALS_INVALID | EXAMT3P_CREDENTIALS_INVALIDES | Garder les deux |

### Solution

Dans `template_engine.py`, la méthode `_select_base_template()` doit gérer les alias. Vérifier que les deux noms fonctionnent.

Alternativement, ajouter un mapping dans `template_engine.py` :

```python
STATE_NAME_ALIASES = {
    'REFUSED_CMA': 'EVALBOX_REFUSE_CMA',
    'VALIDE_CMA_WAITING_CONVOC': 'DATE_FUTURE_VALIDE_CMA',
    'DEADLINE_MISSED': 'DEADLINE_RATEE',
    'CREDENTIALS_INVALID': 'EXAMT3P_CREDENTIALS_INVALIDES',
}
```

---

## 7. Ordre d'Implémentation

### Phase 1 : Entrées Matrice (Priorité Haute)

1. ✅ Ajouter les 10 entrées État×Intention dans `state_intention_matrix.yaml`
2. ✅ Ajouter les 5 nouvelles intentions (I38-I42)

### Phase 2 : Partials (Priorité Haute)

3. ✅ Modifier `partials/intentions/demande_convocation.html` (cas multiples)
4. ✅ Créer `partials/prospect/rappel_inscription.html`
5. ✅ Créer `partials/report/deja_effectue.html`
6. ✅ Modifier `partials/intentions/resultat_examen.html`

### Phase 3 : Nouvelles Intentions (Priorité Moyenne)

7. ✅ Créer `partials/intentions/permis_probatoire.html`
8. ✅ Créer `partials/intentions/changement_departement.html`
9. ✅ Créer `partials/intentions/changement_session.html`
10. ✅ Créer `partials/intentions/date_non_disponible.html`

### Phase 4 : Intégration (Priorité Moyenne)

11. ✅ Modifier `response_master.html` pour intégrer les nouveaux partials
12. ✅ Vérifier propagation des flags dans `template_engine.py`

### Phase 5 : Tests (Obligatoire)

13. ✅ Tester chaque combinaison sur un ticket de test
14. ✅ Vérifier que les fallbacks fonctionnent

---

## 8. Tests de Validation

### Scénarios de Test

| Test | État simulé | Intention | Résultat attendu |
|------|-------------|-----------|------------------|
| T1 | Evalbox="Refusé CMA" | DEMANDE_CONVOCATION | Liste docs refusés + action corriger |
| T2 | Evalbox="Refusé CMA" | REPORT_DATE | Report auto expliqué |
| T3 | Evalbox="Dossier Synchronisé" + J-5 | DEMANDE_CONVOCATION | Alerte report probable |
| T4 | Date_examen=null | DEMANDE_CONVOCATION | Proposer dates d'abord |
| T5 | Evalbox="VALIDE CMA" + J-5 | DEMANDE_CONVOCATION | Alerte anormale + actions urgentes |
| T6 | Stage="EN ATTENTE" | STATUT_DOSSIER | Réponse + rappel inscription |
| T7 | Evalbox="Convoc CMA reçue" | RESULTAT_EXAMEN | Examen pas encore passé |
| T8 | Message "facture" | - | Route vers Backoffice |
| T9 | Message "permis probatoire fin juin" | - | Proposer dates après juin |
| T10 | Message "changer département 93" | - | Selon timing (avant/après compte) |

### Commande de Test

```bash
python test_state_engine_sections.py
```

Ou test manuel :

```bash
python test_doc_workflow_with_examt3p.py <ticket_id>
```

---

## Notes Importantes

1. **ExamT3P est la source de vérité** - Le système synchronise automatiquement vers Zoho
2. **Toujours détailler les documents refusés** avec motif + solution
3. **Ne jamais bloquer les prospects** - répondre + rappeler inscription
4. **Multi-intentions** - toujours répondre aux deux
5. **J-7 = seuil critique** pour convocation et validation

---

## Fichiers Modifiés (Résumé)

| Fichier | Type de modification |
|---------|---------------------|
| `states/state_intention_matrix.yaml` | Ajout entrées matrice + intentions |
| `states/templates/partials/intentions/demande_convocation.html` | Modification majeure |
| `states/templates/partials/intentions/resultat_examen.html` | Modification |
| `states/templates/partials/prospect/rappel_inscription.html` | Création |
| `states/templates/partials/report/deja_effectue.html` | Création |
| `states/templates/partials/intentions/permis_probatoire.html` | Création |
| `states/templates/partials/intentions/changement_departement.html` | Création |
| `states/templates/partials/intentions/changement_session.html` | Création |
| `states/templates/partials/intentions/date_non_disponible.html` | Création |
| `states/templates/response_master.html` | Modification (section prospect) |
| `src/state_engine/template_engine.py` | Vérification flags + alias |
