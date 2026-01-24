#!/usr/bin/env python3
"""
Module d'extraction des données exament3p.fr
Version: 2.0
Date: 05/01/2026

Extrait l'ensemble des données du portail ExamenT3P :
- Données principales du dossier (8 champs)
- Progression du dossier (6 étapes)
- Pièces justificatives (5 obligatoires + 2 optionnelles)
- Détail du paiement (4 champs)
- Actions requises
- Historique des statuts

Voir EXAMENT3P_CHAMPS.md pour la documentation complète.
"""

import re
from typing import Dict, List, Optional
from datetime import datetime


class Exament3pExtractor:
    """Extracteur de données depuis exament3p.fr."""

    # Statuts principaux possibles
    STATUTS_PRINCIPAUX = [
        "En cours de composition",
        "En attente du paiement",
        "En cours d'instruction",
        "Incomplet",
        "Valide"
    ]

    # Documents obligatoires
    DOCUMENTS_OBLIGATOIRES = [
        "Pièce d'identité",
        "Photo d'identité",
        "Signature",
        "Justificatif de domicile ou attestation d'hébérgement",
        "Permis de conduire"
    ]

    # Documents optionnels
    DOCUMENTS_OPTIONNELS = [
        "Pièce d'identité - Justificatif FACULTATIF",
        "Permis de conduire - Justificatif FACULTATIF"
    ]

    def __init__(self, num_dossier: str, identifiant: str = None, password: str = None):
        """
        Initialise l'extracteur.

        Args:
            num_dossier: Numéro de dossier (ex: "00016066")
            identifiant: Email du candidat
            password: Mot de passe
        """
        self.num_dossier = num_dossier
        self.identifiant = identifiant
        self.password = password

    def extract_from_markdown(self, markdown_content: str) -> Dict:
        """
        Extrait toutes les données depuis le contenu Markdown de la page Mon Espace.

        Args:
            markdown_content: Contenu Markdown extrait par le navigateur

        Returns:
            Dictionnaire avec toutes les données extraites
        """
        data = {
            # 1. Données principales
            'num_dossier': self.num_dossier,
            'nom_complet': self._extract_nom_complet(markdown_content),
            'type_examen': self._extract_type_examen(markdown_content),
            'type_epreuve': self._extract_type_epreuve(markdown_content),
            'departement': self._extract_departement(markdown_content),
            'statut_principal': self._extract_statut_principal(markdown_content),
            'date_reception': self._extract_date_reception(markdown_content),
            'date_session': self._extract_date_session(markdown_content),

            # 2. Progression du dossier
            'progression': self._extract_progression(markdown_content),

            # 3. Pièces justificatives
            'pieces_justificatives': self._extract_pieces_justificatives(markdown_content),

            # 4. Paiement
            'paiement': self._extract_paiement(markdown_content),

            # 5. Actions requises
            'actions_requises': self._extract_actions_requises(markdown_content),

            # 6. Historique des statuts
            'historique_statuts': self._extract_historique_statuts(markdown_content),

            # 7. Messages
            'messages': self._extract_messages(markdown_content)
        }

        return data

    # ... (rest of the code from the user's script)
