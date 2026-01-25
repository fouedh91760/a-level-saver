#!/usr/bin/env python3
"""
Test de la synchronisation ExamT3P → CRM.

Usage:
    python test_examt3p_sync.py <DEAL_ID>
    python test_examt3p_sync.py <DEAL_ID> --dry-run

Ce script:
1. Récupère le deal CRM
2. Extrait les données ExamT3P (avec identifiants du deal)
3. Affiche le mapping qui serait appliqué
4. Avec --dry-run: ne fait pas la mise à jour CRM
"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.zoho_client import ZohoCRMClient
from src.agents.examt3p_agent import ExamT3PAgent
from src.utils.examt3p_crm_sync import sync_examt3p_to_crm, determine_evalbox_from_examt3p

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_sync(deal_id: str, dry_run: bool = True):
    """Test la synchronisation ExamT3P → CRM pour un deal."""

    print("\n" + "=" * 70)
    print(f"TEST SYNC EXAMT3P → CRM")
    print(f"Deal ID: {deal_id}")
    print(f"Mode: {'DRY RUN (simulation)' if dry_run else '⚠️  MISE À JOUR RÉELLE'}")
    print("=" * 70)

    # 1. Récupérer le deal CRM
    print("\n1️⃣  Récupération du deal CRM...")
    crm_client = ZohoCRMClient()
    deal_data = crm_client.get_deal(deal_id)

    if not deal_data:
        print(f"❌ Deal {deal_id} non trouvé")
        return

    deal_name = deal_data.get('Deal_Name', 'N/A')
    current_evalbox = deal_data.get('Evalbox', 'N/A')
    identifiant = deal_data.get('IDENTIFIANT_EVALBOX', '')
    password = deal_data.get('MDP_EVALBOX', '')

    print(f"   Deal: {deal_name}")
    print(f"   Evalbox actuel: {current_evalbox}")
    print(f"   Identifiant CRM: {identifiant or '(vide)'}")
    print(f"   MDP CRM: {'***' if password else '(vide)'}")

    # 2. Vérifier si on a les identifiants
    if not identifiant or not password:
        print("\n⚠️  Identifiants ExamT3P manquants dans le CRM")
        print("   Impossible de tester la synchronisation sans identifiants")
        return

    # 3. Extraire les données ExamT3P
    print("\n2️⃣  Extraction des données ExamT3P...")
    examt3p_agent = ExamT3PAgent()

    try:
        examt3p_result = examt3p_agent.process({
            'username': identifiant,
            'password': password
        })

        if not examt3p_result.get('success'):
            print(f"❌ Échec extraction: {examt3p_result.get('error', 'Erreur inconnue')}")
            return

        print("   ✅ Données ExamT3P extraites")

        # Afficher les données clés
        statut_dossier = examt3p_result.get('statut_dossier', 'N/A')
        print(f"\n   📊 DONNÉES EXAMT3P:")
        print(f"   • Statut du Dossier: {statut_dossier}")
        print(f"   • Compte existe: {examt3p_result.get('compte_existe', False)}")

        # Afficher d'autres champs si disponibles
        if examt3p_result.get('prochaine_session'):
            print(f"   • Prochaine session: {examt3p_result.get('prochaine_session')}")
        if examt3p_result.get('documents_manquants'):
            print(f"   • Documents manquants: {examt3p_result.get('documents_manquants')}")

    except Exception as e:
        print(f"❌ Erreur extraction: {e}")
        return

    # 4. Déterminer le mapping
    print("\n3️⃣  Détermination du mapping Evalbox...")
    new_evalbox = determine_evalbox_from_examt3p(examt3p_result)

    if new_evalbox:
        print(f"\n   📊 MAPPING:")
        print(f"   ExamT3P '{statut_dossier}' → Evalbox '{new_evalbox}'")

        if new_evalbox == current_evalbox:
            print(f"\n   ℹ️  Pas de changement (Evalbox déjà à jour)")
        else:
            print(f"\n   🔄 CHANGEMENT DÉTECTÉ:")
            print(f"   Evalbox: '{current_evalbox}' → '{new_evalbox}'")
    else:
        print(f"\n   ⚠️  Aucun mapping trouvé pour '{statut_dossier}'")

    # 5. Exécuter la synchronisation
    print("\n4️⃣  Synchronisation...")

    # Ajouter compte_existe pour que la sync fonctionne
    examt3p_result['compte_existe'] = True

    sync_result = sync_examt3p_to_crm(
        deal_id=deal_id,
        deal_data=deal_data,
        examt3p_data=examt3p_result,
        crm_client=crm_client,
        dry_run=dry_run
    )

    print(f"\n   📋 RÉSULTAT SYNC:")
    print(f"   • Sync effectuée: {sync_result.get('sync_performed', False)}")
    print(f"   • CRM mis à jour: {sync_result.get('crm_updated', False)}")

    if sync_result.get('changes_made'):
        print(f"\n   ✅ CHANGEMENTS {'(simulés)' if dry_run else 'APPLIQUÉS'}:")
        for change in sync_result['changes_made']:
            field = change['field']
            old_val = change.get('old_value', '')
            new_val = change.get('new_value', '')
            if 'MDP' in field:
                new_val = '***'
            print(f"   • {field}: '{old_val}' → '{new_val}'")

    if sync_result.get('blocked_changes'):
        print(f"\n   🔒 CHANGEMENTS BLOQUÉS:")
        for blocked in sync_result['blocked_changes']:
            print(f"   • {blocked['field']}: {blocked['reason']}")

    if not dry_run and sync_result.get('crm_updated'):
        print(f"\n   ✅ CRM MIS À JOUR AVEC SUCCÈS")

        # Vérifier la mise à jour
        print("\n5️⃣  Vérification...")
        updated_deal = crm_client.get_deal(deal_id)
        if updated_deal:
            new_crm_evalbox = updated_deal.get('Evalbox', 'N/A')
            print(f"   Evalbox après mise à jour: {new_crm_evalbox}")

    print("\n" + "=" * 70)
    print("TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_examt3p_sync.py <DEAL_ID> [--dry-run]")
        print("\nExemple:")
        print("  python test_examt3p_sync.py 1234567890 --dry-run  # Simulation")
        print("  python test_examt3p_sync.py 1234567890             # Mise à jour réelle")
        sys.exit(1)

    deal_id = sys.argv[1]
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv

    # Par défaut, dry_run = True pour éviter les erreurs
    if '--force' not in sys.argv and not dry_run:
        print("⚠️  Mode mise à jour réelle détecté")
        print("   Ajoutez --dry-run pour simuler ou --force pour confirmer")
        dry_run = True

    test_sync(deal_id, dry_run=dry_run)
