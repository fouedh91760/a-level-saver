"""
Test de détection HORS_PARTENARIAT basé sur le montant CRM.

Vérifie que la détection utilise Amount du deal et non plus juste "vtc" dans le texte.
"""
from knowledge_base.scenarios_mapping import detect_scenario_from_text


def test_hors_partenariat_detection():
    """Test différents cas de détection HORS_PARTENARIAT."""
    print("\n" + "=" * 80)
    print("TEST DÉTECTION HORS_PARTENARIAT")
    print("=" * 80)

    test_cases = [
        {
            "name": "CAS 1: Uber partnership (20€)",
            "subject": "Formation VTC pour examen",
            "message": "Bonjour, je voudrais m'inscrire pour la formation VTC",
            "crm_data": {"Amount": 20},
            "expected": [],  # Pas HORS_PARTENARIAT car 20€
            "should_contain": False
        },
        {
            "name": "CAS 2: Taxi (50€)",
            "subject": "Formation taxi",
            "message": "Je veux passer le taxi",
            "crm_data": {"Amount": 50},
            "expected": ["SC-HORS_PARTENARIAT"],
            "should_contain": True
        },
        {
            "name": "CAS 3: VTC hors Uber (100€)",
            "subject": "Formation VTC",
            "message": "Formation VTC pour mon entreprise",
            "crm_data": {"Amount": 100},
            "expected": ["SC-HORS_PARTENARIAT", "SC-VTC_HORS_PARTENARIAT"],
            "should_contain": True
        },
        {
            "name": "CAS 4: Ambulance (150€)",
            "subject": "Formation ambulance",
            "message": "Inscription formation ambulance",
            "crm_data": {"Amount": 150},
            "expected": ["SC-HORS_PARTENARIAT"],
            "should_contain": True
        },
        {
            "name": "CAS 5: Nouveau candidat Uber (Amount = 0 pas encore défini)",
            "subject": "Demande d'information VTC Uber",
            "message": "Je voudrais des informations sur la formation VTC Uber",
            "crm_data": {"Amount": 0},
            "expected": [],  # 0 = pas encore défini, pas HORS_PARTENARIAT
            "should_contain": False
        },
        {
            "name": "CAS 6: VTC Uber explicite dans texte (20€)",
            "subject": "Formation VTC Uber",
            "message": "Je suis chauffeur Uber et je veux passer le VTC",
            "crm_data": {"Amount": 20},
            "expected": [],  # 20€ = partenariat Uber OK
            "should_contain": False
        },
        {
            "name": "CAS 7: Mots-clés explicites (taxi) même sans CRM",
            "subject": "Formation taxi",
            "message": "Je veux devenir chauffeur de taxi",
            "crm_data": None,  # Pas de données CRM
            "expected": ["SC-HORS_PARTENARIAT"],
            "should_contain": True
        },
        {
            "name": "CAS 8: VTC dans texte mais pas de CRM data (ne devrait PAS détecter)",
            "subject": "Question sur formation VTC",
            "message": "Informations sur VTC",
            "crm_data": None,
            "expected": [],  # Sans CRM data, on ne peut pas savoir
            "should_contain": False
        }
    ]

    passed = 0
    failed = 0

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'-' * 80}")
        print(f"TEST {i}: {case['name']}")
        print(f"{'-' * 80}")

        scenarios = detect_scenario_from_text(
            subject=case['subject'],
            customer_message=case['message'],
            crm_data=case['crm_data']
        )

        print(f"Sujet: {case['subject']}")
        print(f"Message: {case['message']}")
        print(f"CRM Amount: {case['crm_data'].get('Amount') if case['crm_data'] else 'N/A'}")
        print(f"\nScénarios détectés: {scenarios}")
        print(f"Attendu: {case['expected']}")

        # Check result
        is_hors_partenariat = any("HORS_PARTENARIAT" in s for s in scenarios)

        if case['should_contain']:
            if is_hors_partenariat:
                print("✅ CORRECT: HORS_PARTENARIAT détecté comme attendu")
                passed += 1
            else:
                print("❌ ÉCHEC: HORS_PARTENARIAT devrait être détecté")
                failed += 1
        else:
            if not is_hors_partenariat:
                print("✅ CORRECT: HORS_PARTENARIAT non détecté comme attendu")
                passed += 1
            else:
                print("❌ ÉCHEC: HORS_PARTENARIAT ne devrait PAS être détecté")
                failed += 1

    # Summary
    print(f"\n{'=' * 80}")
    print("RÉSUMÉ")
    print(f"{'=' * 80}")
    print(f"✅ Tests réussis: {passed}/{len(test_cases)}")
    print(f"❌ Tests échoués: {failed}/{len(test_cases)}")

    if failed == 0:
        print("\n🎉 Tous les tests passent ! La détection HORS_PARTENARIAT est correcte.")
    else:
        print(f"\n⚠️  {failed} test(s) ont échoué, vérifier la logique.")

    print(f"\n{'=' * 80}")


if __name__ == "__main__":
    test_hors_partenariat_detection()
