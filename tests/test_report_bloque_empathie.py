"""
Test du template report_bloque avec empathie pour force majeure.

Ce test vérifie que:
1. Le bloc empathie s'affiche correctement selon le type de force majeure
2. Le bloc report s'adapte si force majeure déjà mentionnée
3. Les infos jour examen ne s'affichent PAS
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_report_bloque_avec_deces():
    """Test: Demande de report avec mention de décès."""
    print("=" * 60)
    print("TEST: Report bloqué avec DÉCÈS mentionné")
    print("=" * 60)

    from src.state_engine import StateDetector, TemplateEngine
    from src.state_engine.state_detector import DetectedState

    detector = StateDetector()
    engine = TemplateEngine()

    # Simuler un candidat qui demande un report avec mention de décès
    # IMPORTANT: Tous les champs Uber doivent être valides pour éviter les états Uber
    # IMPORTANT: Date_Cloture_Inscription dans le passé → can_modify_exam_date=false
    deal_data = {
        'Deal_Name': 'Ousman KEBBEH',
        'Amount': 20,
        'Stage': 'GAGNÉ',
        'Evalbox': 'VALIDE CMA',  # Dossier validé
        'Date_examen_VTC': {'name': '75_2026-01-27', 'id': '123'},
        'Contact_Name': {'name': 'Ousman KEBBEH'},
        'Date_Dossier_re_u': '2025-12-01',  # Documents reçus
        'Date_test_selection': '2025-12-05',  # Test passé
        'Compte_Uber': True,  # Compte Uber OK
        'ELIGIBLE': True,  # Éligible Uber
        'Date_Cloture_Inscription': '2026-01-20',  # Clôture PASSÉE → report bloqué
    }

    examt3p_data = {
        'compte_existe': True,
        'connection_test_success': True,
        'identifiant': 'ousman@example.com',
        'mot_de_passe': 'xxx',
    }

    # Triage avec force majeure DÉCÈS détectée
    triage_result = {
        'action': 'GO',
        'detected_intent': 'REPORT_DATE',
        'intent_context': {
            'mentions_force_majeure': True,
            'force_majeure_type': 'death',
            'force_majeure_details': 'décès du beau-père de son assistante maternelle',
            'is_urgent': True,
            'wants_earlier_date': False
        }
    }

    linking_result = {
        'deal_id': '123456',
        'has_duplicate_uber_offer': False,
    }

    # Détecter l'état
    state = detector.detect_state(
        deal_data=deal_data,
        examt3p_data=examt3p_data,
        triage_result=triage_result,
        linking_result=linking_result
    )

    print(f"\n📊 État détecté: {state.name} ({state.id})")
    print(f"   Catégorie: {state.category}")

    # Vérifier que le contexte contient les bonnes variables
    ctx = state.context_data
    print(f"\n📋 Contexte force majeure:")
    print(f"   mentions_force_majeure: {ctx.get('mentions_force_majeure')}")
    print(f"   force_majeure_type: {ctx.get('force_majeure_type')}")
    print(f"   is_force_majeure_deces: {ctx.get('is_force_majeure_deces')}")
    print(f"   is_force_majeure_medical: {ctx.get('is_force_majeure_medical')}")

    # Enrichir le contexte avec le prénom
    state.context_data['prenom'] = 'Ousman'

    # Générer la réponse
    result = engine.generate_response(state)

    response = result.get('response_text', '')
    template_used = result.get('template_used', '')
    blocks = result.get('blocks_included', [])

    print(f"\n📝 Template utilisé: {template_used}")
    print(f"📦 Blocs inclus: {blocks}")

    print("\n" + "-" * 60)
    print("RÉPONSE GÉNÉRÉE:")
    print("-" * 60)
    print(response)
    print("-" * 60)

    # Vérifications
    errors = []

    # 1. Doit contenir message d'empathie pour décès
    if "condoléances" in response.lower() or "triste nouvelle" in response.lower():
        print("\n✅ Message d'empathie pour décès présent")
    else:
        errors.append("Message d'empathie pour décès ABSENT")

    # 2. Doit reconnaître la force majeure
    if "cas de force majeure" in response.lower() or "demande de report est bien prise en compte" in response.lower():
        print("✅ Reconnaissance de la force majeure")
    else:
        errors.append("Reconnaissance de la force majeure ABSENTE")

    # 3. Doit demander le certificat de décès spécifiquement
    if "certificat" in response.lower() and "décès" in response.lower():
        print("✅ Demande de certificat de décès")
    else:
        errors.append("Demande de certificat de décès ABSENTE")

    # 4. NE DOIT PAS contenir les infos jour examen
    if "jour de l'examen" in response.lower() or "à apporter obligatoirement" in response.lower():
        errors.append("Infos jour examen PRÉSENTES (ne devraient pas l'être)")
    else:
        print("✅ Pas d'infos jour examen (correct)")

    # 5. NE DOIT PAS redemander une explication de la situation
    if "brève explication de votre situation" in response.lower():
        errors.append("Redemande explication (ne devrait pas car FM déjà mentionnée)")
    else:
        print("✅ Ne redemande pas d'explication")

    if errors:
        print("\n❌ ERREURS:")
        for e in errors:
            print(f"   • {e}")
        return False
    else:
        print("\n✅ TEST RÉUSSI!")
        return True


def test_report_bloque_sans_force_majeure():
    """Test: Demande de report SANS mention de force majeure."""
    print("\n" + "=" * 60)
    print("TEST: Report bloqué SANS force majeure mentionnée")
    print("=" * 60)

    from src.state_engine import StateDetector, TemplateEngine

    detector = StateDetector()
    engine = TemplateEngine()

    deal_data = {
        'Deal_Name': 'Jean DUPONT',
        'Amount': 20,
        'Stage': 'GAGNÉ',
        'Evalbox': 'VALIDE CMA',
        'Date_examen_VTC': {'name': '75_2026-01-27', 'id': '123'},
        'Contact_Name': {'name': 'Jean DUPONT'},
        'Date_Dossier_re_u': '2025-12-01',
        'Date_test_selection': '2025-12-05',
        'Compte_Uber': True,
        'ELIGIBLE': True,
        'Date_Cloture_Inscription': '2026-01-20',  # Clôture PASSÉE
    }

    examt3p_data = {'compte_existe': True}

    # Triage SANS force majeure
    triage_result = {
        'action': 'GO',
        'detected_intent': 'REPORT_DATE',
        'intent_context': {
            'mentions_force_majeure': False,
            'force_majeure_type': None,
            'wants_earlier_date': False
        }
    }

    linking_result = {'deal_id': '123456', 'has_duplicate_uber_offer': False}

    state = detector.detect_state(
        deal_data=deal_data,
        examt3p_data=examt3p_data,
        triage_result=triage_result,
        linking_result=linking_result
    )

    state.context_data['prenom'] = 'Jean'

    result = engine.generate_response(state)
    response = result.get('response_text', '')

    print(f"\n📝 Template utilisé: {result.get('template_used')}")
    print("\n" + "-" * 60)
    print("RÉPONSE GÉNÉRÉE:")
    print("-" * 60)
    print(response)
    print("-" * 60)

    errors = []

    # 1. NE DOIT PAS contenir message d'empathie
    if "condoléances" in response.lower() or "désolés d'apprendre" in response.lower():
        errors.append("Message d'empathie présent alors qu'il ne devrait pas")
    else:
        print("\n✅ Pas de message d'empathie (correct)")

    # 2. Doit expliquer la procédure force majeure
    if "force majeure" in response.lower():
        print("✅ Explication force majeure présente")
    else:
        errors.append("Explication force majeure ABSENTE")

    # 3. Doit mentionner le certificat médical ou décès comme exemples
    if "certificat médical" in response.lower() or "certificat de décès" in response.lower():
        print("✅ Exemples de justificatifs présents")
    else:
        errors.append("Exemples de justificatifs ABSENTS")

    # 4. NE DOIT PAS contenir les infos jour examen
    if "jour de l'examen" in response.lower():
        errors.append("Infos jour examen PRÉSENTES")
    else:
        print("✅ Pas d'infos jour examen (correct)")

    if errors:
        print("\n❌ ERREURS:")
        for e in errors:
            print(f"   • {e}")
        return False
    else:
        print("\n✅ TEST RÉUSSI!")
        return True


def test_report_bloque_medical():
    """Test: Demande de report avec problème médical."""
    print("\n" + "=" * 60)
    print("TEST: Report bloqué avec problème MÉDICAL")
    print("=" * 60)

    from src.state_engine import StateDetector, TemplateEngine

    detector = StateDetector()
    engine = TemplateEngine()

    deal_data = {
        'Deal_Name': 'Marie MARTIN',
        'Amount': 20,
        'Stage': 'GAGNÉ',
        'Evalbox': 'VALIDE CMA',
        'Date_examen_VTC': {'name': '75_2026-02-15', 'id': '123'},
        'Date_Dossier_re_u': '2025-12-01',
        'Date_test_selection': '2025-12-05',
        'Compte_Uber': True,
        'ELIGIBLE': True,
        'Date_Cloture_Inscription': '2026-01-20',  # Clôture PASSÉE
    }

    examt3p_data = {'compte_existe': True}

    triage_result = {
        'action': 'GO',
        'detected_intent': 'REPORT_DATE',
        'intent_context': {
            'mentions_force_majeure': True,
            'force_majeure_type': 'medical',
            'force_majeure_details': 'hospitalisée pour une opération',
        }
    }

    linking_result = {'deal_id': '123456', 'has_duplicate_uber_offer': False}

    state = detector.detect_state(
        deal_data=deal_data,
        examt3p_data=examt3p_data,
        triage_result=triage_result,
        linking_result=linking_result
    )

    state.context_data['prenom'] = 'Marie'

    result = engine.generate_response(state)
    response = result.get('response_text', '')

    print(f"\n📝 Template utilisé: {result.get('template_used')}")
    print("\n" + "-" * 60)
    print("RÉPONSE GÉNÉRÉE:")
    print("-" * 60)
    print(response)
    print("-" * 60)

    errors = []

    # Doit contenir message d'empathie pour problème médical
    if "santé" in response.lower() or "rétabli" in response.lower():
        print("\n✅ Message d'empathie médical présent")
    else:
        errors.append("Message d'empathie médical ABSENT")

    # Doit demander certificat médical
    if "certificat médical" in response.lower():
        print("✅ Demande de certificat médical")
    else:
        errors.append("Demande de certificat médical ABSENTE")

    if errors:
        print("\n❌ ERREURS:")
        for e in errors:
            print(f"   • {e}")
        return False
    else:
        print("\n✅ TEST RÉUSSI!")
        return True


if __name__ == "__main__":
    print("\n🚀 TESTS DU TEMPLATE REPORT_BLOQUE AVEC EMPATHIE 🚀\n")

    results = []
    results.append(("Décès mentionné", test_report_bloque_avec_deces()))
    results.append(("Sans force majeure", test_report_bloque_sans_force_majeure()))
    results.append(("Problème médical", test_report_bloque_medical()))

    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
    else:
        print("\n⚠️  Certains tests ont échoué.")
