# Keywords pour Détection d'Envoi de Documents

Liste complète des mots-clés utilisés pour détecter qu'un client envoie des documents.

## 📎 Mots-clés d'envoi générique

- ci-joint
- pièce jointe
- piece jointe
- document
- fichier
- attachment

## 🆔 Documents d'identité

- pièce d'identité
- piece d'identite
- photo d'identité
- photo d'identite
- carte d'identité
- carte d'identite
- CNI
- passeport
- titre de séjour
- titre de sejour
- récépissé de titre de séjour
- recepisse de titre de sejour
- récépissé de permis
- recepisse de permis

## 🏠 Justificatifs de domicile

- justificatif de domicile
- justificatif domicile
- attestation d'hébergement
- attestation d'hebergement
- attestation hebergement
- preuve de domicile
- facture électricité
- facture eau
- facture gaz
- avis d'imposition
- quittance de loyer

## ✍️ Signature et autres

- signature
- signé
- signe

## 🔍 Patterns de détection

Détecter également :
- "vous trouverez en pièce jointe"
- "je vous envoie"
- "ci-dessous"
- "voici le/les document(s)"
- "en attaché"
- "joint à ce mail"

---

## Usage dans le code

```python
DOCUMENT_KEYWORDS = [
    # Générique
    "ci-joint", "ci joint", "pièce jointe", "piece jointe",
    "document", "fichier", "attachment", "attaché",

    # Identité
    "pièce d'identité", "piece d'identite", "photo d'identité",
    "carte d'identité", "cni", "passeport",
    "titre de séjour", "titre de sejour",
    "récépissé", "recepisse",

    # Domicile
    "justificatif de domicile", "justificatif domicile",
    "attestation d'hébergement", "attestation hebergement",
    "preuve de domicile",

    # Autre
    "signature", "signé", "signe"
]

def is_document_submission(thread_content: str) -> bool:
    """Détecte si le thread contient un envoi de documents."""
    content_lower = thread_content.lower()
    return any(keyword in content_lower for keyword in DOCUMENT_KEYWORDS)
```
