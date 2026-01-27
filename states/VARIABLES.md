# Convention des Variables - Templates CAB Formations

## Syntaxe

```
{{variable}}           → Variable simple
{{variable|default}}   → Variable avec valeur par défaut
{{#if condition}}...{{/if}}  → Bloc conditionnel
{{#each items}}...{{/each}}  → Boucle
```

---

## Variables CRM (Deal)

| Variable | Type | Description | Exemple |
|----------|------|-------------|---------|
| `{{prenom}}` | string | Prénom du candidat | "Mohamed" |
| `{{nom}}` | string | Nom du candidat | "Dupont" |
| `{{email}}` | string | Email du contact | "mohamed@email.com" |
| `{{telephone}}` | string | Téléphone | "06 12 34 56 78" |
| `{{stage}}` | string | Étape du deal | "GAGNÉ" |
| `{{amount}}` | number | Montant | 20 |
| `{{evalbox}}` | string | Statut Evalbox | "VALIDE CMA" |
| `{{resultat}}` | string | Résultat examen | "ADMIS" |
| `{{cma_de_depot}}` | string | Département d'inscription | "75" |

---

## Variables Lookup Date_examen_VTC (Module: Dates_Examens_VTC_TAXI)

| Variable | Type | Description | Exemple |
|----------|------|-------------|---------|
| `{{date_examen}}` | date | Date d'examen (formatée JJ/MM/AAAA) | "31/03/2026" |
| `{{date_examen_iso}}` | date | Date d'examen (format ISO) | "2026-03-31" |
| `{{departement_examen}}` | string | Département de l'examen | "75" |
| `{{date_cloture}}` | date | Date clôture inscriptions | "15/03/2026" |
| `{{session_examen_id}}` | string | ID de la session d'examen | "198709000..." |
| `{{session_examen_nom}}` | string | Nom complet de la session | "VTC - 31/03/2026 - 75" |

---

## Variables Lookup Session (Module: Sessions1)

| Variable | Type | Description | Exemple |
|----------|------|-------------|---------|
| `{{session_nom}}` | string | Nom de la session | "cdj-24mars-28mars-2026" |
| `{{session_debut}}` | date | Date début formation | "24/03/2026" |
| `{{session_fin}}` | date | Date fin formation | "28/03/2026" |
| `{{session_type}}` | string | Type : "jour" ou "soir" | "jour" |
| `{{session_horaires}}` | string | Horaires de la session | "8h30 - 16h30" |
| `{{session_lieu}}` | string | Lieu de formation | "VISIO Zoom VTC" |
| `{{session_statut}}` | string | Statut de la session | "PLANIFIÉ" |

---

## Variables ExamT3P

| Variable | Type | Description | Exemple |
|----------|------|-------------|---------|
| `{{identifiant_examt3p}}` | string | Identifiant ExamT3P | "mohamed@email.com" |
| `{{mot_de_passe_examt3p}}` | string | Mot de passe ExamT3P | "Abc123!" |
| `{{statut_dossier}}` | string | Statut sur ExamT3P | "Valide" |
| `{{num_dossier}}` | string | Numéro de dossier CMA | "00038886" |
| `{{compte_existe}}` | bool | Compte ExamT3P existe | true/false |
| `{{paiement_effectue}}` | bool | Paiement CMA fait | true/false |

---

## Variables Calculées

| Variable | Type | Description | Exemple |
|----------|------|-------------|---------|
| `{{jours_avant_examen}}` | number | Jours restants | 15 |
| `{{jours_avant_cloture}}` | number | Jours avant clôture | 5 |
| `{{date_aujourdhui}}` | date | Date du jour | "27/01/2026" |
| `{{prochaines_dates}}` | array | Liste des prochaines dates | voir ci-dessous |
| `{{sessions_proposees}}` | array | Sessions de formation | voir ci-dessous |
| `{{documents_refuses}}` | array | Documents refusés | voir ci-dessous |
| `{{region_candidat}}` | string | Région détectée | "Île-de-France" |

---

## Structures de données

### prochaines_dates
```yaml
- date: "31/03/2026"
  departement: "75"
  cloture: "15/03/2026"
  places_restantes: 45
```

### sessions_proposees
```yaml
- nom: "CDJ - 24 mars - 28 mars 2026"
  type: "jour"
  debut: "24/03/2026"
  fin: "28/03/2026"
  horaires: "8h30 - 16h30"
```

### documents_refuses
```yaml
- nom: "Justificatif de domicile"
  motif: "Document de plus de 3 mois"
```

---

## Liens Officiels (constantes)

| Variable | URL |
|----------|-----|
| `{{lien_examt3p}}` | https://www.exament3p.fr |
| `{{lien_elearning}}` | https://cab-formations.fr/user |
| `{{lien_test_selection}}` | https://cab-formations.fr/user/login?destination=/course/test-de-s%C3%A9lection |
| `{{lien_inscription_uber}}` | https://cab-formations.fr/uberxcab_welcome |

---

## Blocs Conditionnels

```handlebars
{{#if compte_existe}}
  Contenu si compte existe
{{else}}
  Contenu si pas de compte
{{/if}}

{{#if identifiant_examt3p}}
  Vos identifiants : {{identifiant_examt3p}}
{{/if}}

{{#each prochaines_dates}}
  - {{this.date}} (département {{this.departement}})
{{/each}}
```

---

## Règles de Formatage

1. **Dates** : Toujours au format `JJ/MM/AAAA`
2. **Montants** : Ne jamais afficher "20€", dire "frais de dossier"
3. **Liens** : Toujours en markdown cliquable `[Texte](URL)`
4. **Emojis** : Utiliser avec parcimonie pour la clarté
5. **Gras** : Réservé aux éléments vraiment importants
