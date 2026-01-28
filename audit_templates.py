#!/usr/bin/env python3
"""
Audit de couverture : Templates Legacy vs Partials Modulaires
"""

# Mapping des templates legacy vers les partials
MAPPING = {
    # === TEMPLATES UBER ===
    'uber_cas_a.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_cas_a',
        'action': 'envoyer_documents',
        'note': 'Template hybride existe'
    },
    'uber_cas_a_bloque.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_cas_a_bloque',
        'action': 'envoyer_documents',
        'note': ''
    },
    'uber_cas_b.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_cas_b',
        'action': 'passer_test',
        'note': 'Template hybride existe'
    },
    'uber_cas_d.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_cas_d',
        'action': 'contacter_uber',
        'note': ''
    },
    'uber_cas_e.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_cas_e',
        'action': 'contacter_uber',
        'note': ''
    },
    'uber_verif_en_cours.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: uber_verif_en_cours',
        'action': 'AUCUNE',
        'note': ''
    },
    'uber_docs_missing_hybrid.html': {
        'intention': 'MULTI (flags)',
        'statut': 'en_attente',
        'action': 'envoyer_documents',
        'note': 'HYBRIDE OK'
    },
    'uber_test_missing_hybrid.html': {
        'intention': 'MULTI (flags)',
        'statut': 'en_attente',
        'action': 'passer_test',
        'note': 'HYBRIDE OK'
    },

    # === TEMPLATES STATUT DOSSIER ===
    'dossier_cree.html': {
        'intention': 'statut_dossier',
        'statut': 'dossier_cree',
        'action': 'completer_dossier',
        'note': ''
    },
    'dossier_synchronise.html': {
        'intention': 'statut_dossier',
        'statut': 'dossier_synchronise',
        'action': 'surveiller_paiement',
        'note': ''
    },
    'pret_a_payer.html': {
        'intention': 'statut_dossier',
        'statut': 'pret_a_payer',
        'action': 'surveiller_paiement',
        'note': ''
    },
    'valide_cma.html': {
        'intention': 'statut_dossier',
        'statut': 'valide_cma',
        'action': 'attendre_convocation',
        'note': ''
    },
    'convoc_cma_recue.html': {
        'intention': 'statut_dossier',
        'statut': 'convoc_recue',
        'action': 'preparer_examen',
        'note': ''
    },
    'refus_cma.html': {
        'intention': 'statut_dossier',
        'statut': 'refus_cma',
        'action': 'corriger_documents',
        'note': ''
    },
    'refus_cma_docs.html': {
        'intention': 'probleme_documents',
        'statut': 'refus_cma',
        'action': 'corriger_documents',
        'note': ''
    },

    # === TEMPLATES DATES ===
    'date_examen_vide.html': {
        'intention': 'demande_date',
        'statut': 'en_attente',
        'action': 'choisir_date',
        'note': ''
    },
    'propose_dates.html': {
        'intention': 'demande_date',
        'statut': 'AUCUN',
        'action': 'choisir_date',
        'note': ''
    },
    'propose_dates_elargies.html': {
        'intention': 'demande_date',
        'statut': 'AUCUN',
        'action': 'choisir_date',
        'note': ''
    },
    'date_future_en_attente.html': {
        'intention': 'statut_dossier',
        'statut': 'en_attente',
        'action': 'AUCUNE',
        'note': ''
    },
    'date_passee_non_valide.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: date_passee',
        'action': 'choisir_date',
        'note': ''
    },
    'deadline_ratee.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: deadline_ratee',
        'action': 'choisir_date',
        'note': ''
    },
    'deadline_ratee_report.html': {
        'intention': 'report_date',
        'statut': 'A CREER: deadline_ratee',
        'action': 'choisir_date',
        'note': ''
    },

    # === TEMPLATES REPORT ===
    'report_possible.html': {
        'intention': 'report_date',
        'statut': 'DYNAMIQUE',
        'action': 'choisir_date',
        'note': ''
    },
    'report_bloque.html': {
        'intention': 'report_date',
        'statut': 'A CREER: report_bloque',
        'action': 'A CREER: force_majeure',
        'note': ''
    },
    'report_valide_cma.html': {
        'intention': 'report_date',
        'statut': 'valide_cma',
        'action': 'A CREER: frais_report',
        'note': ''
    },
    'report_force_majeure_procedure.html': {
        'intention': 'report_date',
        'statut': 'AUCUN',
        'action': 'A CREER: envoyer_justificatif',
        'note': ''
    },
    'valide_cma_report_auto.html': {
        'intention': 'report_date',
        'statut': 'valide_cma',
        'action': 'AUCUNE',
        'note': ''
    },

    # === TEMPLATES CREDENTIALS ===
    'credentials_inconnus.html': {
        'intention': 'demande_identifiants',
        'statut': 'AUCUN',
        'action': 'A CREER: fournir_ids',
        'note': ''
    },
    'credentials_invalid.html': {
        'intention': 'demande_identifiants',
        'statut': 'AUCUN',
        'action': 'A CREER: verifier_ids',
        'note': ''
    },
    'credentials_refused.html': {
        'intention': 'A CREER: refus_partage',
        'statut': 'AUCUN',
        'action': 'A CREER: autonomie',
        'note': ''
    },
    'credentials_refused_security.html': {
        'intention': 'A CREER: refus_partage',
        'statut': 'AUCUN',
        'action': 'A CREER: autonomie',
        'note': ''
    },
    'demande_identifiants.html': {
        'intention': 'demande_identifiants',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'convocation_identifiants.html': {
        'intention': 'demande_identifiants',
        'statut': 'convoc_recue',
        'action': 'preparer_examen',
        'note': ''
    },

    # === TEMPLATES CONVOCATION ===
    'attente_convocation.html': {
        'intention': 'demande_convocation',
        'statut': 'valide_cma',
        'action': 'attendre_convocation',
        'note': ''
    },

    # === TEMPLATES SESSION ===
    'confirmation_session.html': {
        'intention': 'confirmation_session',
        'statut': 'DYNAMIQUE',
        'action': 'AUCUNE',
        'note': ''
    },
    'confirmation_date.html': {
        'intention': 'demande_date',
        'statut': 'DYNAMIQUE',
        'action': 'choisir_session',
        'note': ''
    },
    'rafraichissement_session.html': {
        'intention': 'A CREER: formation',
        'statut': 'A CREER: formation_terminee',
        'action': 'A CREER: rafraichissement',
        'note': ''
    },
    'lien_visio.html': {
        'intention': 'A CREER: lien_visio',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },

    # === TEMPLATES RESULTAT ===
    'resultat_admis.html': {
        'intention': 'A CREER: resultat',
        'statut': 'A CREER: admis',
        'action': 'A CREER: carte_vtc',
        'note': ''
    },
    'resultat_admis_carte.html': {
        'intention': 'A CREER: carte_vtc',
        'statut': 'A CREER: admis',
        'action': 'A CREER: carte_vtc',
        'note': ''
    },
    'resultat_admissible.html': {
        'intention': 'A CREER: resultat',
        'statut': 'A CREER: admissible',
        'action': 'A CREER: pratique',
        'note': ''
    },
    'resultat_non_admis.html': {
        'intention': 'A CREER: resultat',
        'statut': 'A CREER: non_admis',
        'action': 'A CREER: reinscription',
        'note': ''
    },
    'resultat_non_admissible.html': {
        'intention': 'A CREER: resultat',
        'statut': 'A CREER: non_admissible',
        'action': 'A CREER: reinscription',
        'note': ''
    },
    'resultat_absent.html': {
        'intention': 'A CREER: resultat',
        'statut': 'A CREER: absent',
        'action': 'A CREER: reinscription',
        'note': ''
    },
    'reinscription.html': {
        'intention': 'A CREER: reinscription',
        'statut': 'AUCUN',
        'action': 'A CREER: reinscription',
        'note': ''
    },

    # === TEMPLATES PROSPECT ===
    'prospect.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: prospect',
        'action': 'A CREER: finaliser',
        'note': ''
    },
    'prospect_confirmation_paiement.html': {
        'intention': 'A CREER: paiement',
        'statut': 'A CREER: prospect',
        'action': 'A CREER: finaliser',
        'note': ''
    },
    'prospect_demande_dates.html': {
        'intention': 'demande_date',
        'statut': 'A CREER: prospect',
        'action': 'A CREER: finaliser',
        'note': ''
    },

    # === TEMPLATES DOCUMENTS ===
    'docs_manquants.html': {
        'intention': 'probleme_documents',
        'statut': 'A CREER: docs_manquants',
        'action': 'completer_dossier',
        'note': ''
    },
    'docs_refuses.html': {
        'intention': 'probleme_documents',
        'statut': 'A CREER: docs_refuses',
        'action': 'corriger_documents',
        'note': ''
    },

    # === TEMPLATES DIVERS ===
    'no_compte_examt3p.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: pas_de_compte',
        'action': 'choisir_date',
        'note': ''
    },
    'elearning_access.html': {
        'intention': 'demande_elearning',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'pas_recu_email.html': {
        'intention': 'A CREER: email',
        'statut': 'AUCUN',
        'action': 'A CREER: spams',
        'note': ''
    },
    'examen_passe.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: examen_passe',
        'action': 'A CREER: attendre_resultat',
        'note': ''
    },
    'clarification_examen.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: examen_passe',
        'action': 'AUCUNE',
        'note': ''
    },

    # === TEMPLATES COMMUNICATION ===
    'demande_appel.html': {
        'intention': 'A CREER: appel',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'demande_remboursement.html': {
        'intention': 'A CREER: remboursement',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'reclamation.html': {
        'intention': 'A CREER: reclamation',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'annulation.html': {
        'intention': 'A CREER: annulation',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'doublon_uber.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: doublon_uber',
        'action': 'A CREER: autonome',
        'note': ''
    },
    'deal_perdu.html': {
        'intention': 'statut_dossier',
        'statut': 'A CREER: deal_perdu',
        'action': 'AUCUNE',
        'note': ''
    },

    # === TEMPLATES SIMPLES ===
    'salutation.html': {
        'intention': 'A CREER: salutation',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'message_confus.html': {
        'intention': 'A CREER: confus',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'remerciement.html': {
        'intention': 'A CREER: merci',
        'statut': 'AUCUN',
        'action': 'AUCUNE',
        'note': ''
    },
    'statut_dossier_reponse.html': {
        'intention': 'statut_dossier',
        'statut': 'DYNAMIQUE',
        'action': 'DYNAMIQUE',
        'note': 'COMPLEXE'
    },
}

def main():
    # Partials existants
    existants = {
        'intentions': ['confirmation_session', 'demande_convocation', 'demande_date',
                      'demande_elearning', 'demande_identifiants', 'probleme_documents',
                      'report_date', 'statut_dossier'],
        'statuts': ['convoc_recue', 'dossier_cree', 'dossier_synchronise', 'en_attente',
                   'pret_a_payer', 'refus_cma', 'valide_cma'],
        'actions': ['attendre_convocation', 'choisir_date', 'choisir_session',
                   'completer_dossier', 'contacter_uber', 'corriger_documents',
                   'envoyer_documents', 'passer_test', 'preparer_examen', 'surveiller_paiement']
    }

    # Collecter les partials a creer
    a_creer = {'intentions': set(), 'statuts': set(), 'actions': set()}

    for tpl, mapping in MAPPING.items():
        for key, cat in [('intention', 'intentions'), ('statut', 'statuts'), ('action', 'actions')]:
            val = mapping[key]
            if 'A CREER' in val:
                name = val.replace('A CREER: ', '')
                a_creer[cat].add(name)

    print('=' * 80)
    print('AUDIT DE COUVERTURE : TEMPLATES LEGACY vs PARTIALS MODULAIRES')
    print('=' * 80)
    print()

    print('PARTIALS EXISTANTS:')
    print(f'  Intentions ({len(existants["intentions"])}): {existants["intentions"]}')
    print(f'  Statuts ({len(existants["statuts"])}): {existants["statuts"]}')
    print(f'  Actions ({len(existants["actions"])}): {existants["actions"]}')
    print(f'  TOTAL: {sum(len(v) for v in existants.values())} partials')
    print()

    print('PARTIALS A CREER:')
    print(f'  Intentions ({len(a_creer["intentions"])}): {sorted(a_creer["intentions"])}')
    print(f'  Statuts ({len(a_creer["statuts"])}): {sorted(a_creer["statuts"])}')
    print(f'  Actions ({len(a_creer["actions"])}): {sorted(a_creer["actions"])}')
    print(f'  TOTAL: {sum(len(v) for v in a_creer.values())} partials')
    print()

    print('=' * 80)
    print('TABLEAU DE MAPPING DETAILLE')
    print('=' * 80)
    print()
    print(f'{"Template Legacy":<40} | {"Intention":<20} | {"Statut":<20} | {"Action":<20}')
    print('-' * 105)

    for tpl in sorted(MAPPING.keys()):
        m = MAPPING[tpl]
        intention = m['intention'][:20]
        statut = m['statut'][:20]
        action = m['action'][:20]
        print(f'{tpl:<40} | {intention:<20} | {statut:<20} | {action:<20}')

    print()
    print('=' * 80)
    print('RESUME')
    print('=' * 80)
    print(f'Templates legacy: {len(MAPPING)}')
    print(f'Partials existants: {sum(len(v) for v in existants.values())}')
    print(f'Partials a creer: {sum(len(v) for v in a_creer.values())}')
    print()

    # Calculer couverture
    couverts = 0
    for tpl, m in MAPPING.items():
        if 'A CREER' not in m['intention'] and 'A CREER' not in m['statut'] and 'A CREER' not in m['action']:
            couverts += 1

    print(f'Templates DEJA COUVERTS par partials existants: {couverts}/{len(MAPPING)}')
    print(f'Templates NECESSITANT nouveaux partials: {len(MAPPING) - couverts}/{len(MAPPING)}')


if __name__ == '__main__':
    main()
