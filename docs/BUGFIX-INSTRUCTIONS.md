# Instructions pour corriger les bugs Multi-Intention/Multi-État

Lis CLAUDE.md et analyse les fichiers suivants pour corriger 6 bugs dans l'architecture multi-intention/multi-état :

## FICHIERS À ANALYSER
- src/state_engine/state_detector.py
- src/state_engine/template_engine.py

## BUGS À CORRIGER

### BUG 1 (CRITIQUE) : _match_consistency_state() code mort
Dans state_detector.py, les méthodes `_match_consistency_state()` et `_match_session_state()` retournent toujours False (ont des `pass`). Implémente la logique en utilisant `training_exam_consistency_data` du contexte.

### BUG 2 (CRITIQUE) : Secondary intents ignorés
Dans state_detector.py, `_match_intent_state()` ne vérifie que `detected_intent`. Ajoute la vérification des `secondary_intents`.

### BUG 3 : Section0 override incomplet
Dans template_engine.py, `_auto_map_intention_flags()` applique `section0_overrides` au primary_intent mais PAS aux secondary_intents. Corrige pour éviter les doublons.

### BUG 4 : Context flags manquants PASS 2-5
Dans template_engine.py, `_select_base_template()` n'injecte `context_flags` que dans PASS 0 et 1. Ajoute l'injection dans tous les PASS (1.5, 2, 3, 4, 5, fallback).

### BUG 5 : Filtrage sessions incomplet
Dans template_engine.py, le filtrage sessions vérifie seulement si `detected_intent == 'CONFIRMATION_SESSION'`. Vérifie aussi `secondary_intents`.

### BUG 6 : Standardiser primary_intent
Remplace les usages incohérents de `detected_intent`/`primary_intent` par un standard unique. Garder `detected_intent` uniquement comme alias pour rétrocompatibilité.

## PROCESS
1. Montre-moi le PLAN avant de coder
2. Attends ma validation
3. Implémente et commite chaque fix séparément

## CONTRAINTES
- Ne PAS casser la rétrocompatibilité
- Ajouter des logs DEBUG
- Documenter les changements dans les docstrings
