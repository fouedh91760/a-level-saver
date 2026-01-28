# Diagrammes d'Architecture - A-Level Saver

Ce document contient les diagrammes Mermaid décrivant l'architecture et les flux du système A-Level Saver.

---

## 1. Vue d'Ensemble de l'Architecture

```mermaid
graph TB
    subgraph "Sources de Données Externes"
        ZD[Zoho Desk<br/>Tickets]
        ZC[Zoho CRM<br/>Deals & Contacts]
        ET[ExamT3P<br/>Plateforme CMA]
    end

    subgraph "Couche API"
        ZDC[ZohoDeskClient]
        ZCC[ZohoCRMClient]
        ETA[ExamT3PAgent]
    end

    subgraph "Agents Spécialisés"
        TA[TriageAgent<br/>GO/ROUTE/SPAM]
        DLA[DealLinkingAgent<br/>Liaison CRM]
        CUA[CRMUpdateAgent<br/>Mises à jour CRM]
        DA[DispatcherAgent<br/>Routage]
    end

    subgraph "Helpers & Utils"
        DEH[DateExamenHelper<br/>10 cas d'analyse]
        SH[SessionHelper<br/>Sélection sessions]
        UEH[UberEligibilityHelper<br/>Cas A/B/D/E]
        ECH[ExamT3PCredentialsHelper<br/>Extraction identifiants]
        AH[AlertsHelper<br/>Alertes temporaires]
    end

    subgraph "State Engine"
        SD[StateDetector<br/>~25 états]
        TE[TemplateEngine<br/>Handlebars]
        RV[ResponseValidator<br/>Validation règles]
    end

    subgraph "Orchestration"
        WF[DOCTicketWorkflow<br/>8 étapes]
    end

    subgraph "Données d'État"
        CS[(candidate_states.yaml<br/>~25 états)]
        SIM[(state_intention_matrix.yaml<br/>37 intentions)]
        TPL[(templates/<br/>~62 templates HTML)]
        BLK[(blocks/<br/>~50 blocs MD)]
    end

    ZD --> ZDC
    ZC --> ZCC
    ET --> ETA

    ZDC --> WF
    ZCC --> WF
    ETA --> WF

    WF --> TA
    WF --> DLA
    WF --> CUA
    WF --> DA

    WF --> DEH
    WF --> SH
    WF --> UEH
    WF --> ECH
    WF --> AH

    WF --> SD
    SD --> TE
    TE --> RV

    CS --> SD
    SIM --> SD
    SIM --> TE
    TPL --> TE
    BLK --> TE

    style WF fill:#e1f5fe
    style SD fill:#fff3e0
    style TE fill:#fff3e0
    style TA fill:#f3e5f5
    style DLA fill:#f3e5f5
    style CUA fill:#f3e5f5
```

---

## 2. Workflow Principal - Traitement des Tickets DOC

```mermaid
flowchart TD
    START([Ticket DOC reçu]) --> T1

    subgraph TRIAGE["ÉTAPE 1: TRIAGE"]
        T1[TriageAgent analyse<br/>sujet + threads]
        T1 --> T2{Action?}
        T2 -->|SPAM| SPAM[Clôturer ticket]
        T2 -->|ROUTE| ROUTE[Transférer vers<br/>autre département]
        T2 -->|GO| LINK
    end

    subgraph LINKING["ÉTAPE 2: LIAISON CRM"]
        LINK[DealLinkingAgent<br/>cherche deal CRM]
        LINK --> LINK2{Deal trouvé?}
        LINK2 -->|Non| NODEAL[Créer deal ou<br/>escalader]
        LINK2 -->|Oui| DUP{Doublon<br/>Uber 20€?}
        DUP -->|Oui| DUPLICATE[Réponse spéciale<br/>doublon]
        DUP -->|Non| ANALYSIS
    end

    subgraph ANALYSIS["ÉTAPE 3: ANALYSE 6 SOURCES"]
        direction TB
        A1[ExamT3P Data<br/>sync identifiants]
        A2[CRM Data<br/>deal_data]
        A3[Date Examen<br/>10 cas possibles]
        A4[Sessions<br/>jour/soir]
        A5[Uber Eligibility<br/>Cas A/B/D/E]
        A6[Consistency<br/>formation/examen]
        A1 --> MERGE
        A2 --> MERGE
        A3 --> MERGE
        A4 --> MERGE
        A5 --> MERGE
        A6 --> MERGE
        MERGE[Fusion contexte]
    end

    MERGE --> STATE

    subgraph STATE_ENGINE["ÉTAPE 4-5: STATE ENGINE"]
        STATE[StateDetector<br/>détermine état]
        STATE --> INTENT[Combinaison<br/>ÉTAT × INTENTION]
        INTENT --> TPL[Sélection template<br/>via matrice]
        TPL --> RENDER[TemplateEngine<br/>rendu Handlebars]
        RENDER --> VALIDATE[ResponseValidator<br/>vérification règles]
    end

    VALIDATE --> NOTE

    subgraph OUTPUTS["ÉTAPES 6-8: SORTIES"]
        NOTE[Note CRM consolidée<br/>next steps IA]
        NOTE --> DRAFT[Brouillon Zoho Desk]
        DRAFT --> UPDATE[Updates CRM<br/>via CRMUpdateAgent]
        UPDATE --> FINAL[Mise à jour ticket<br/>tags + statut]
    end

    SPAM --> END([Fin])
    ROUTE --> END
    DUPLICATE --> END
    NODEAL --> END
    FINAL --> END

    style TRIAGE fill:#e8f5e9
    style LINKING fill:#e3f2fd
    style ANALYSIS fill:#fff8e1
    style STATE_ENGINE fill:#fce4ec
    style OUTPUTS fill:#f3e5f5
```

---

## 3. Machine à États - Détection d'État du Candidat

```mermaid
stateDiagram-v2
    [*] --> TRIAGE_STATES

    state TRIAGE_STATES {
        SPAM: T1 - SPAM
        ROUTE: T2 - ROUTE
        DUPLICATE_UBER: T3 - Doublon Uber
        CANDIDATE_NOT_FOUND: T4 - Candidat introuvable
    }

    state ANALYSIS_STATES {
        CREDENTIALS_INVALID: A0 - Identifiants invalides
        EXAMT3P_DOWN: A1 - ExamT3P indisponible
        SYNC_ERROR: A2 - Erreur synchronisation
    }

    state UBER_ELIGIBILITY {
        U_PROSPECT: Prospect non payé
        U_CAS_A: Payé mais docs manquants
        U_CAS_B: Docs OK mais test manquant
        U_CAS_D: Compte Uber non vérifié
        U_CAS_E: Non éligible Uber
        U_ELIGIBLE: Éligible complet
    }

    state EXAM_DATE_STATES {
        D_EMPTY: Date vide
        D_PAST: Date passée
        D_REFUSED: Refusé CMA
        D_VALIDE: VALIDE CMA
        D_SYNCED: Dossier synchronisé
        D_CONVOC: Convocation reçue
        D_BLOCKED: Modification bloquée
    }

    state INTENTION_STATES {
        I_STATUS: Statut dossier
        I_DATE: Demande date
        I_CREDS: Demande identifiants
        I_SESSION: Confirmation session
        I_REPORT: Report date
        I_CONVOC: Demande convocation
    }

    TRIAGE_STATES --> ANALYSIS_STATES: Si GO
    ANALYSIS_STATES --> UBER_ELIGIBILITY: Si données valides
    UBER_ELIGIBILITY --> EXAM_DATE_STATES: Si éligible
    EXAM_DATE_STATES --> INTENTION_STATES: Selon intention détectée
    INTENTION_STATES --> [*]: Réponse générée

    note right of TRIAGE_STATES
        Priorité 1-99
        Décision immédiate
    end note

    note right of UBER_ELIGIBILITY
        Priorité 200-299
        Uniquement deals 20€
    end note

    note right of EXAM_DATE_STATES
        Priorité 300-399
        10 cas possibles
    end note
```

---

## 4. Flux de Données - De la Source au Template

```mermaid
flowchart LR
    subgraph SOURCES["Sources de Données"]
        ZD[(Zoho Desk)]
        ZC[(Zoho CRM)]
        ET[(ExamT3P)]
    end

    subgraph EXTRACTION["Extraction"]
        TH[Threads ticket<br/>get_all_threads]
        DD[Deal data<br/>get_deal]
        ED[ExamT3P data<br/>extract_data]
    end

    subgraph ANALYSIS["Analyse"]
        TA[TriageAgent<br/>→ intention]
        DEH[DateHelper<br/>→ cas 1-10]
        SH[SessionHelper<br/>→ sessions dispo]
        UEH[UberHelper<br/>→ cas A/B/D/E]
    end

    subgraph CONTEXT["Contexte Unifié"]
        CTX{{"context = {<br/>  deal_data,<br/>  examt3p_data,<br/>  intention,<br/>  exam_analysis,<br/>  session_data,<br/>  uber_case,<br/>  alerts<br/>}"}}
    end

    subgraph STATE["State Engine"]
        SD[StateDetector]
        M[(Matrice<br/>État×Intention)]
        SD --> |lookup| M
    end

    subgraph TEMPLATE["Rendu Template"]
        TPL[Template HTML<br/>+ Partials]
        HB[Handlebars<br/>substitution]
        VAL[Validation<br/>règles métier]
    end

    subgraph OUTPUT["Sortie"]
        RESP[Réponse HTML<br/>finale]
    end

    ZD --> TH
    ZC --> DD
    ET --> ED

    TH --> TA
    DD --> DEH
    DD --> SH
    DD --> UEH
    ED --> DEH
    ED --> SH

    TA --> CTX
    DEH --> CTX
    SH --> CTX
    UEH --> CTX

    CTX --> SD
    SD --> TPL
    M --> TPL
    TPL --> HB
    HB --> VAL
    VAL --> RESP

    style CTX fill:#fff3e0
    style SD fill:#e8f5e9
    style HB fill:#e3f2fd
```

---

## 5. Cas Uber 20€ - Arbre de Décision

```mermaid
flowchart TD
    START([Deal Amount = 20€]) --> STAGE{Stage?}

    STAGE -->|Non GAGNÉ| PROSPECT[U-PROSPECT<br/>Prospect non payé]
    STAGE -->|GAGNÉ| DOCS{Date_Dossier_recu?}

    DOCS -->|Vide| CAS_A[U-CAS-A<br/>Docs manquants<br/>→ Demander documents]
    DOCS -->|Rempli| TEST{Date_test_selection?<br/>ET après 19/05/2025}

    TEST -->|Vide ET > 19/05| CAS_B[U-CAS-B<br/>Test manquant<br/>→ Passer le test]
    TEST -->|Rempli OU < 19/05| VERIF{J+1 après<br/>Date_Dossier_recu?}

    VERIF -->|Non| WAIT[Vérification en attente<br/>→ Ne pas bloquer]
    VERIF -->|Oui| COMPTE{Compte_Uber?}

    COMPTE -->|false| CAS_D[U-CAS-D<br/>Compte non vérifié<br/>→ Contacter Uber]
    COMPTE -->|true| ELIGIBLE_CHECK{ELIGIBLE?}

    ELIGIBLE_CHECK -->|false| CAS_E[U-CAS-E<br/>Non éligible<br/>→ Contacter Uber]
    ELIGIBLE_CHECK -->|true| ELIGIBLE[ELIGIBLE<br/>✓ Peut s'inscrire]

    ELIGIBLE --> EXAM_FLOW[Flux inscription<br/>examen normal]

    style PROSPECT fill:#fff3e0
    style CAS_A fill:#ffcdd2
    style CAS_B fill:#ffcdd2
    style CAS_D fill:#ffcdd2
    style CAS_E fill:#ffcdd2
    style ELIGIBLE fill:#c8e6c9
    style WAIT fill:#e1f5fe
```

---

## 6. Agents et Leurs Responsabilités

```mermaid
graph TB
    subgraph "Agents IA (Claude)"
        TA[<b>TriageAgent</b><br/>━━━━━━━━━━━━<br/>• Classifie GO/ROUTE/SPAM<br/>• Détecte intention I01-I37<br/>• Extrait contexte urgence<br/>• Préférence session jour/soir]

        DLA[<b>DealLinkingAgent</b><br/>━━━━━━━━━━━━<br/>• Lie ticket → deal CRM<br/>• Détecte doublons Uber<br/>• Récupère deal_data<br/>• Gère cas multi-deals]

        CUA[<b>CRMUpdateAgent</b><br/>━━━━━━━━━━━━<br/>• Mapping string → ID<br/>• Règles de blocage<br/>• Updates sécurisés<br/>• Logging automatique]

        ETA[<b>ExamT3PAgent</b><br/>━━━━━━━━━━━━<br/>• Extraction données CMA<br/>• Statut dossier<br/>• Documents/paiements<br/>• Playwright backup]
    end

    subgraph "Helpers Fonctionnels"
        DEH[<b>DateExamenHelper</b><br/>━━━━━━━━━━━━<br/>• 10 cas de date<br/>• Dates alternatives<br/>• Filtrage par région<br/>• Règles de blocage]

        SH[<b>SessionHelper</b><br/>━━━━━━━━━━━━<br/>• Sessions jour/soir<br/>• Auto-sélection<br/>• Proposition options<br/>• Matching date→session]

        UEH[<b>UberEligibilityHelper</b><br/>━━━━━━━━━━━━<br/>• Cas A/B/D/E<br/>• Vérification timing<br/>• Messages adaptés<br/>• Règles de blocage]

        ECH[<b>CredentialsHelper</b><br/>━━━━━━━━━━━━<br/>• Extraction via IA<br/>• Validation connexion<br/>• Source CRM/threads<br/>• Gestion double compte]
    end

    TA --> |intention| WF[DOCTicketWorkflow]
    DLA --> |deal_data| WF
    CUA --> |updates| WF
    ETA --> |examt3p_data| WF

    DEH --> |exam_analysis| WF
    SH --> |session_data| WF
    UEH --> |uber_case| WF
    ECH --> |credentials| WF

    style TA fill:#e1bee7
    style DLA fill:#e1bee7
    style CUA fill:#e1bee7
    style ETA fill:#e1bee7
    style DEH fill:#b3e5fc
    style SH fill:#b3e5fc
    style UEH fill:#b3e5fc
    style ECH fill:#b3e5fc
    style WF fill:#c8e6c9
```

---

## 7. Template Engine - Sélection et Rendu

```mermaid
flowchart TD
    subgraph INPUT["Entrées"]
        STATE[État détecté<br/>ex: VALIDE_CMA]
        INTENT[Intention détectée<br/>ex: STATUT_DOSSIER]
        CTX[Contexte données<br/>deal, examt3p, etc.]
    end

    subgraph SELECTION["Sélection Template"]
        direction TB
        P0{PASS 0<br/>Matrice État:Intention?}
        P1{PASS 1<br/>Template avec<br/>for_intention?}
        P2{PASS 1.5<br/>Template avec<br/>for_state?}
        P3{PASS 2<br/>Template avec<br/>for_condition?}
        P4{PASS 3<br/>Cas Uber?}
        P5{PASS 4<br/>Résultat examen?}
        P6{PASS 5<br/>Evalbox status?}
        P7[FALLBACK<br/>Par nom d'état]

        P0 -->|Non trouvé| P1
        P1 -->|Non trouvé| P2
        P2 -->|Non trouvé| P3
        P3 -->|Non trouvé| P4
        P4 -->|Non trouvé| P5
        P5 -->|Non trouvé| P6
        P6 -->|Non trouvé| P7
    end

    subgraph RENDERING["Rendu Handlebars"]
        TPL[Template base<br/>.html]
        PART[Partials<br/>intentions/statuts/actions]
        BLK[Blocs<br/>salutation, signature]

        TPL --> MERGE_TPL
        PART --> MERGE_TPL
        BLK --> MERGE_TPL

        MERGE_TPL[Template compilé]

        MERGE_TPL --> IF["{{#if}} resolution"]
        IF --> EACH["{{#each}} loops"]
        EACH --> VAR["{{variable}} substitution"]
        VAR --> PARTIAL["{{> partial}} inclusion"]
    end

    subgraph VALIDATION["Validation"]
        V1[Termes interdits?<br/>BFS, Evalbox, API...]
        V2[Blocs requis?<br/>salutation, signature]
        V3[Données inventées?<br/>dates, montants...]
        V4[Format HTML valide?]
    end

    STATE --> P0
    INTENT --> P0
    CTX --> MERGE_TPL

    P0 -->|Trouvé| TPL
    P1 -->|Trouvé| TPL
    P2 -->|Trouvé| TPL
    P3 -->|Trouvé| TPL
    P4 -->|Trouvé| TPL
    P5 -->|Trouvé| TPL
    P6 -->|Trouvé| TPL
    P7 --> TPL

    PARTIAL --> V1
    V1 --> V2 --> V3 --> V4
    V4 --> OUTPUT[Réponse HTML validée]

    style P0 fill:#c8e6c9
    style MERGE_TPL fill:#fff3e0
    style OUTPUT fill:#e1f5fe
```

---

## 8. Synchronisation ExamT3P ↔ CRM

```mermaid
sequenceDiagram
    participant WF as Workflow
    participant ECH as CredentialsHelper
    participant ETA as ExamT3PAgent
    participant SYNC as ExamT3PCRMSync
    participant CRM as Zoho CRM

    WF->>ECH: get_credentials_with_validation()

    alt Credentials dans CRM
        ECH->>CRM: Récupérer IDENTIFIANT/MDP_EVALBOX
        CRM-->>ECH: identifiants
    else Extraction depuis threads
        ECH->>ECH: Analyse IA (Haiku)<br/>des threads
        ECH-->>ECH: identifiants extraits
    end

    ECH->>ETA: Test connexion ExamT3P
    ETA-->>ECH: connection_test_success

    ECH-->>WF: credentials + compte_existe

    WF->>ETA: extract_data(id, mdp)
    ETA-->>WF: examt3p_data

    WF->>SYNC: sync_examt3p_to_crm()

    SYNC->>SYNC: Mapping statut<br/>ExamT3P → Evalbox

    Note over SYNC: "En attente paiement" → "Pret a payer"<br/>"En cours instruction" → "Dossier Synchronisé"<br/>"Valide" → "VALIDE CMA"

    SYNC->>SYNC: Check can_modify_exam_date?

    alt VALIDE CMA + deadline passée
        SYNC-->>WF: Modification bloquée
    else Modification possible
        SYNC->>SYNC: find_exam_session_by_date_and_dept()
        SYNC->>CRM: update_deal(session_id, evalbox, etc.)
        CRM-->>SYNC: OK
    end

    SYNC-->>WF: sync_result
```

---

## 9. Architecture Modulaire des Templates

```mermaid
graph TB
    subgraph MASTER["response_master.html"]
        SAL[Salutation personnalisée]

        subgraph SECTION1["Section 1: Réponse Intention"]
            I1[intention_statut_dossier]
            I2[intention_demande_date]
            I3[intention_confirmation_session]
            I4[intention_report_date]
            I5[intention_demande_identifiants]
        end

        subgraph SECTION2["Section 2: Statut Actuel"]
            S1[evalbox_dossier_cree]
            S2[evalbox_dossier_synchronise]
            S3[evalbox_valide_cma]
            S4[evalbox_convoc_recue]
            S5[evalbox_refus_cma]
        end

        subgraph SECTION3["Section 3: Action Requise"]
            A1[action_passer_test]
            A2[action_choisir_date]
            A3[action_choisir_session]
            A4[action_surveiller_paiement]
            A5[action_preparer_examen]
        end

        subgraph SECTION4["Section 4: Dates/Sessions"]
            D1[Liste next_dates]
            D2[Sessions proposées]
        end

        SIG[Signature + rappels]
    end

    subgraph PARTIALS["states/templates/partials/"]
        PI[intentions/*.html]
        PS[statuts/*.html]
        PA[actions/*.html]
    end

    subgraph BLOCKS["states/blocks/"]
        B1[salutation_personnalisee.md]
        B2[signature.md]
        B3[prochaines_dates_examen.md]
        B4[identifiants_examt3p.md]
    end

    SAL --> B1
    SECTION1 --> PI
    SECTION2 --> PS
    SECTION3 --> PA
    SIG --> B2

    style MASTER fill:#e3f2fd
    style SECTION1 fill:#fff3e0
    style SECTION2 fill:#e8f5e9
    style SECTION3 fill:#fce4ec
    style SECTION4 fill:#f3e5f5
```

---

## 10. Cycle de Vie d'un Ticket DOC

```mermaid
stateDiagram-v2
    [*] --> NOUVEAU: Ticket créé

    state "Phase Triage" as TRIAGE {
        NOUVEAU --> ANALYSE_TRIAGE: TriageAgent
        ANALYSE_TRIAGE --> SPAM_DETECTED: Action=SPAM
        ANALYSE_TRIAGE --> ROUTE_DETECTED: Action=ROUTE
        ANALYSE_TRIAGE --> GO_DETECTED: Action=GO
    }

    SPAM_DETECTED --> CLOTURE_SPAM: Clôturer auto
    ROUTE_DETECTED --> TRANSFERE: Déplacer dept

    state "Phase Analyse" as ANALYSE {
        GO_DETECTED --> LIAISON_CRM: DealLinkingAgent
        LIAISON_CRM --> DOUBLON: Doublon Uber détecté
        LIAISON_CRM --> ANALYSE_SOURCES: Deal trouvé
        ANALYSE_SOURCES --> DATA_READY: 6 sources analysées
    }

    DOUBLON --> REPONSE_DOUBLON: Message spécial

    state "Phase Génération" as GEN {
        DATA_READY --> DETECTION_ETAT: StateDetector
        DETECTION_ETAT --> SELECTION_TPL: Matrice État×Intention
        SELECTION_TPL --> RENDU: TemplateEngine
        RENDU --> VALIDATION: ResponseValidator
    }

    state "Phase Sortie" as OUT {
        VALIDATION --> NOTE_CRM: Création note
        NOTE_CRM --> DRAFT: Brouillon Desk
        DRAFT --> UPDATE_CRM: CRMUpdateAgent
        UPDATE_CRM --> PRET_ENVOI: Tags + statut
    }

    PRET_ENVOI --> [*]: En attente validation humaine
    CLOTURE_SPAM --> [*]
    TRANSFERE --> [*]
    REPONSE_DOUBLON --> [*]
```

---

## 11. Intentions Détectées par TriageAgent (I01-I37)

```mermaid
mindmap
  root((37 Intentions))
    Statut & Info
      I01 STATUT_DOSSIER
      I02 DEMANDE_CONVOCATION
      I03 DEMANDE_FACTURE
      I04 QUESTION_GENERALE
    Dates & Sessions
      I10 DEMANDE_DATE_EXAMEN
      I11 CONFIRMATION_DATE
      I12 REPORT_DATE
      I13 CONFIRMATION_SESSION
      I14 CHANGEMENT_SESSION
    Identifiants
      I20 DEMANDE_IDENTIFIANTS
      I21 PROBLEME_CONNEXION
      I22 MDP_OUBLIE
    Documents
      I30 ENVOI_DOCUMENTS
      I31 PROBLEME_DOCUMENTS
      I32 DOCUMENTS_MANQUANTS
    Formation
      I40 ACCES_ELEARNING
      I41 PROBLEME_ELEARNING
      I42 QUESTION_FORMATION
    Paiement
      I50 QUESTION_PAIEMENT
      I51 PROBLEME_PAIEMENT
      I52 DEMANDE_REMBOURSEMENT
    Spécial
      I60 FORCE_MAJEURE
      I61 ANNULATION
      I37 SUPPRESSION_DONNEES_RGPD
```

---

## 12. Règles de Blocage - Modification Date Examen

```mermaid
flowchart TD
    START([Demande modification<br/>Date_examen_VTC]) --> CHECK1{Evalbox?}

    CHECK1 -->|VALIDE CMA<br/>ou Convoc reçue| CHECK2{Date_Cloture<br/>passée?}
    CHECK1 -->|Autre statut| ALLOWED[✓ Modification<br/>autorisée]

    CHECK2 -->|Oui| BLOCKED[✗ BLOQUÉ<br/>Inscription finalisée<br/>auprès de la CMA]
    CHECK2 -->|Non| ALLOWED

    BLOCKED --> FM{Force majeure<br/>justifiée?}

    FM -->|Oui| MANUAL[Action manuelle<br/>requise<br/>avec justificatif]
    FM -->|Non| REFUSE[Refuser la demande<br/>Expliquer impossibilité]

    ALLOWED --> UPDATE[Proposer nouvelles dates<br/>via CRMUpdateAgent]

    style BLOCKED fill:#ffcdd2
    style ALLOWED fill:#c8e6c9
    style MANUAL fill:#fff3e0
    style REFUSE fill:#ffcdd2
```

---

## 13. Stack Technologique

```mermaid
graph TB
    subgraph "Frontend/Interface"
        ZD[Zoho Desk UI]
        ZC[Zoho CRM UI]
    end

    subgraph "APIs Externes"
        ZD_API[Zoho Desk API]
        ZC_API[Zoho CRM API]
        ET_API[ExamT3P Web]
        CLAUDE[Claude API<br/>Anthropic]
    end

    subgraph "Application Python"
        subgraph "Clients API"
            ZDC[ZohoDeskClient]
            ZCC[ZohoCRMClient]
            ETA[ExamT3PAgent<br/>+ Playwright]
        end

        subgraph "Agents IA"
            TA[TriageAgent<br/>Haiku 3.5]
            RW[Response Writer<br/>Sonnet 4.5]
            NS[Next Steps<br/>Haiku 3.5]
        end

        subgraph "State Engine"
            SE[StateDetector<br/>+ TemplateEngine]
        end

        subgraph "Config"
            ENV[.env + config.py]
            YAML[(YAML configs)]
        end
    end

    subgraph "Données Locales"
        CS[(candidate_states.yaml)]
        SIM[(state_intention_matrix.yaml)]
        TPL[(templates/*.html)]
        BLK[(blocks/*.md)]
        SCHEMA[(crm_schema.json)]
    end

    ZD --> ZD_API
    ZC --> ZC_API

    ZD_API --> ZDC
    ZC_API --> ZCC
    ET_API --> ETA
    CLAUDE --> TA
    CLAUDE --> RW
    CLAUDE --> NS

    CS --> SE
    SIM --> SE
    TPL --> SE
    BLK --> SE

    style CLAUDE fill:#e1bee7
    style SE fill:#fff3e0
    style ZDC fill:#b3e5fc
    style ZCC fill:#b3e5fc
```

---

## Légende

| Couleur | Signification |
|---------|---------------|
| 🟢 Vert clair | Flux principal / OK |
| 🔵 Bleu clair | Données / APIs |
| 🟡 Jaune/Orange | Analyse / Traitement |
| 🟣 Violet | IA / Agents Claude |
| 🔴 Rouge clair | Blocage / Erreur |
| ⬜ Gris | Éléments neutres |

---

*Généré automatiquement depuis l'analyse du codebase A-Level Saver*
