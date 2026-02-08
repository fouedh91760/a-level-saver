"""Tests for ThreadMemory module."""

import pytest
from datetime import datetime, timedelta
from src.utils.thread_memory import (
    parse_meta_line,
    extract_meta_records_from_notes,
    analyze_thread_memory,
    parse_timeline,
    _detect_human_intervention,
    MetaRecord,
    ThreadMemoryResult,
    FieldChange,
    HumanIntervention,
)


# ─── parse_meta_line tests ───

class TestParseMetaLine:
    def test_full_meta_line(self):
        line = "[META] ticket=198709000449714052 | ts=2026-02-07T14:30 | state=VALIDE_CMA_WAITING_CONVOC | intent=DEMANDE_STATUT_DOSSIER | evalbox=VALIDE CMA | date_exam=2026-03-31 | sections=statut,dates,identifiants"
        record = parse_meta_line(line)
        assert record is not None
        assert record.ticket_id == '198709000449714052'
        assert record.timestamp == datetime(2026, 2, 7, 14, 30)
        assert record.state == 'VALIDE_CMA_WAITING_CONVOC'
        assert record.intent == 'DEMANDE_STATUT_DOSSIER'
        assert record.evalbox == 'VALIDE CMA'
        assert record.date_exam == '2026-03-31'
        assert record.sections == ['statut', 'dates', 'identifiants']

    def test_minimal_meta_line(self):
        line = "[META] ticket=123 | ts=2026-02-07T10:00 | state=READY_TO_PAY | intent=SUIVI_DOSSIER"
        record = parse_meta_line(line)
        assert record is not None
        assert record.ticket_id == '123'
        assert record.state == 'READY_TO_PAY'
        assert record.intent == 'SUIVI_DOSSIER'
        assert record.sections == []

    def test_with_secondary_intents(self):
        line = "[META] ticket=123 | ts=2026-02-07T10:00 | state=X | intent=A | intents_sec=B,C | evalbox=N/A"
        record = parse_meta_line(line)
        assert record is not None
        assert record.secondary_intents == ['B', 'C']

    def test_with_session(self):
        line = "[META] ticket=123 | ts=2026-02-07T10:00 | state=X | intent=A | session=jour 2026-04-13/2026-04-24"
        record = parse_meta_line(line)
        assert record is not None
        assert record.session == 'jour 2026-04-13/2026-04-24'

    def test_with_date_case(self):
        line = "[META] ticket=123 | ts=2026-02-07T10:00 | state=X | intent=A | date_case=2"
        record = parse_meta_line(line)
        assert record is not None
        assert record.date_case == '2'

    def test_empty_string(self):
        assert parse_meta_line('') is None

    def test_no_meta_tag(self):
        assert parse_meta_line('This is a normal note line') is None

    def test_meta_with_no_pairs(self):
        assert parse_meta_line('[META]') is None

    def test_malformed_pairs(self):
        line = "[META] not_a_pair | also_not"
        assert parse_meta_line(line) is None

    def test_meta_embedded_in_note(self):
        line = "Some prefix [META] ticket=123 | ts=2026-02-07T10:00 | state=X | intent=A"
        record = parse_meta_line(line)
        assert record is not None
        assert record.ticket_id == '123'


# ─── extract_meta_records_from_notes tests ───

class TestExtractMetaRecords:
    def _make_notes_response(self, notes_content_list):
        """Helper to build a mock notes API response."""
        return {
            "data": [
                {"Note_Title": "Test", "Note_Content": content}
                for content in notes_content_list
            ]
        }

    def test_single_note_with_meta(self):
        response = self._make_notes_response([
            "[META] ticket=1 | ts=2026-02-05T10:00 | state=X | intent=A | evalbox=N/A\nRest of note content"
        ])
        records = extract_meta_records_from_notes(response)
        assert len(records) == 1
        assert records[0].ticket_id == '1'

    def test_multiple_notes_sorted(self):
        response = self._make_notes_response([
            "[META] ticket=2 | ts=2026-02-07T10:00 | state=Y | intent=B | evalbox=Pret a payer",
            "[META] ticket=1 | ts=2026-02-05T10:00 | state=X | intent=A | evalbox=N/A",
        ])
        records = extract_meta_records_from_notes(response)
        assert len(records) == 2
        # Oldest first
        assert records[0].ticket_id == '1'
        assert records[1].ticket_id == '2'

    def test_notes_without_meta(self):
        response = self._make_notes_response([
            "Just a regular CRM note without META",
            "Another note\nWith multiple lines",
        ])
        records = extract_meta_records_from_notes(response)
        assert len(records) == 0

    def test_mixed_notes(self):
        response = self._make_notes_response([
            "Regular note",
            "[META] ticket=1 | ts=2026-02-05T10:00 | state=X | intent=A | evalbox=N/A\nContent",
            "Another regular note",
        ])
        records = extract_meta_records_from_notes(response)
        assert len(records) == 1

    def test_empty_response(self):
        assert extract_meta_records_from_notes({}) == []
        assert extract_meta_records_from_notes(None) == []
        assert extract_meta_records_from_notes({"data": []}) == []

    def test_invalid_data_format(self):
        assert extract_meta_records_from_notes({"data": "not a list"}) == []
        assert extract_meta_records_from_notes({"data": [None, 42, "string"]}) == []


# ─── Suppression flags tests ───

class TestSuppressionFlags:
    def _make_notes(self, sections, evalbox='N/A', date_exam='N/A', intent='SUIVI_DOSSIER'):
        """Helper to build notes with a single META record."""
        sections_str = ','.join(sections) if sections else ''
        ts = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
        content = f"[META] ticket=1 | ts={ts} | state=X | intent={intent} | evalbox={evalbox} | date_exam={date_exam} | sections={sections_str}"
        return {"data": [{"Note_Title": "Test", "Note_Content": content}]}

    def test_suppress_previously_communicated(self):
        notes = self._make_notes(['identifiants', 'dates', 'sessions'])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_identifiants is True
        assert result.suppress_dates is True
        assert result.suppress_sessions is True

    def test_no_suppress_if_not_communicated(self):
        notes = self._make_notes(['identifiants'])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_identifiants is True
        assert result.suppress_dates is False  # Not communicated before
        assert result.suppress_sessions is False

    def test_no_suppress_if_intent_protects(self):
        notes = self._make_notes(['identifiants', 'dates'])
        deal = {'Evalbox': 'N/A'}
        # ENVOIE_IDENTIFIANTS protects 'identifiants' section
        result = analyze_thread_memory(notes, deal, 'ENVOIE_IDENTIFIANTS')
        assert result.suppress_identifiants is False  # Protected by intent
        assert result.suppress_dates is True  # Not protected

    def test_no_suppress_if_evalbox_changed(self):
        notes = self._make_notes(['statut', 'paiement'], evalbox='Pret a payer')
        deal = {'Evalbox': 'VALIDE CMA'}  # Changed!
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_statut is False  # Evalbox changed
        assert result.suppress_paiement is False  # Also linked to evalbox

    def test_no_suppress_if_date_exam_changed(self):
        notes = self._make_notes(['dates'], date_exam='2026-03-31')
        deal = {'Evalbox': 'N/A', 'Date_examen_VTC': '34_2026-05-26'}  # Changed!
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_dates is False  # Date changed

    def test_suppress_elearning(self):
        notes = self._make_notes(['elearning'])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_elearning is True

    def test_empty_sections_no_suppress(self):
        notes = self._make_notes([])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_identifiants is False
        assert result.suppress_dates is False


# ─── Progression detection tests ───

class TestProgression:
    def _make_notes(self, evalbox='N/A', date_exam='N/A'):
        ts = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
        content = f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox={evalbox} | date_exam={date_exam} | sections=statut"
        return {"data": [{"Note_Title": "Test", "Note_Content": content}]}

    def test_evalbox_progression(self):
        notes = self._make_notes(evalbox='Pret a payer')
        deal = {'Evalbox': 'Dossier Synchronisé'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.evalbox_changed is True
        assert result.evalbox_previous == 'Pret a payer'
        assert result.evalbox_current == 'Dossier Synchronisé'

    def test_no_evalbox_progression(self):
        notes = self._make_notes(evalbox='Pret a payer')
        deal = {'Evalbox': 'Pret a payer'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.evalbox_changed is False
        assert result.evalbox_previous == ''

    def test_date_exam_change(self):
        notes = self._make_notes(date_exam='2026-03-31')
        deal = {'Evalbox': 'N/A', 'Date_examen_VTC': '34_2026-05-26'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.date_exam_changed is True
        assert result.date_exam_previous == '2026-03-31'
        assert result.date_exam_current == '2026-05-26'


# ─── Relance detection tests ───

class TestRelanceDetection:
    def _make_notes(self, hours_ago=24):
        ts = (datetime.now() - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M')
        content = f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox=N/A | sections=statut"
        return {"data": [{"Note_Title": "Test", "Note_Content": content}]}

    def _make_threads(self, incoming_hours_ago_list):
        """Create mock threads with specified timestamps."""
        threads = []
        for hours_ago in incoming_hours_ago_list:
            ts = (datetime.now() - timedelta(hours=hours_ago)).isoformat()
            threads.append({
                'direction': 'in',
                'createdTime': ts,
            })
        return threads

    def test_relance_detected(self):
        # We responded 48h ago, candidate wrote 12h ago
        notes = self._make_notes(hours_ago=48)
        threads = self._make_threads([12])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', threads)
        assert result.is_relance is True
        assert result.unanswered_count == 1
        assert result.days_since_last >= 1

    def test_no_relance_if_no_threads_after(self):
        # We responded 12h ago, no new messages
        notes = self._make_notes(hours_ago=12)
        threads = self._make_threads([24])  # Thread is BEFORE our response
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', threads)
        assert result.is_relance is False
        assert result.unanswered_count == 0

    def test_no_relance_if_same_day(self):
        # We responded 2h ago, candidate wrote 1h ago (same day, not really a relance)
        notes = self._make_notes(hours_ago=2)
        threads = self._make_threads([1])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', threads)
        # days_since_last = 0, so is_relance requires >= 1 day
        assert result.is_relance is False

    def test_no_relance_no_history(self):
        notes = {"data": []}
        threads = self._make_threads([12])
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', threads)
        assert result.is_relance is False
        assert result.has_history is False

    def test_no_threads(self):
        notes = self._make_notes(hours_ago=48)
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', None)
        assert result.is_relance is False


# ─── Graceful degradation tests ───

class TestGracefulDegradation:
    def test_none_notes(self):
        result = analyze_thread_memory(None, {}, 'SUIVI_DOSSIER')
        assert result.has_history is False
        assert result.suppress_dates is False
        assert result.is_relance is False

    def test_empty_deal_data(self):
        ts = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
        notes = {"data": [{"Note_Title": "T", "Note_Content": f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox=N/A | sections=statut"}]}
        result = analyze_thread_memory(notes, {}, 'SUIVI_DOSSIER')
        assert result.has_history is True
        # Should not crash

    def test_malformed_note_content(self):
        notes = {"data": [{"Note_Title": "T", "Note_Content": "[META] garbage data here"}]}
        result = analyze_thread_memory(notes, {}, 'SUIVI_DOSSIER')
        # Should not crash
        assert isinstance(result, ThreadMemoryResult)


# ─── Integration scenario tests ───

class TestIntegrationScenarios:
    def test_first_interaction(self):
        """No META records → no history, no suppression."""
        notes = {"data": [{"Note_Title": "Welcome", "Note_Content": "Regular note without META"}]}
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.has_history is False
        assert result.suppress_identifiants is False
        assert result.is_relance is False

    def test_second_interaction_same_state(self):
        """Same state, same data → suppress previously communicated sections."""
        ts = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
        notes = {"data": [{"Note_Title": "T", "Note_Content":
            f"[META] ticket=1 | ts={ts} | state=READY_TO_PAY | intent=SUIVI_DOSSIER | evalbox=Pret a payer | date_exam=2026-03-31 | sections=statut,dates,identifiants,sessions"
        }]}
        deal = {'Evalbox': 'Pret a payer', 'Date_examen_VTC': '34_2026-03-31'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.has_history is True
        assert result.suppress_identifiants is True
        assert result.suppress_dates is True
        assert result.suppress_sessions is True
        assert result.suppress_statut is True
        assert result.evalbox_changed is False

    def test_second_interaction_evalbox_progressed(self):
        """Evalbox changed → don't suppress statut, do suppress other unchanged sections."""
        ts = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
        notes = {"data": [{"Note_Title": "T", "Note_Content":
            f"[META] ticket=1 | ts={ts} | state=READY_TO_PAY | intent=SUIVI_DOSSIER | evalbox=Pret a payer | sections=statut,identifiants"
        }]}
        deal = {'Evalbox': 'Dossier Synchronisé'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER')
        assert result.suppress_statut is False  # Evalbox changed
        assert result.suppress_identifiants is True  # No change for identifiants
        assert result.evalbox_changed is True
        assert result.evalbox_previous == 'Pret a payer'
        assert result.evalbox_current == 'Dossier Synchronisé'

    def test_frustrated_candidate_relance(self):
        """Candidate relances after 3 days without answer."""
        ts = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        notes = {"data": [{"Note_Title": "T", "Note_Content":
            f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox=N/A | sections=statut"
        }]}
        thread_ts = (datetime.now() - timedelta(hours=6)).isoformat()
        threads = [{'direction': 'in', 'createdTime': thread_ts}]
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', threads)
        assert result.is_relance is True
        assert result.days_since_last >= 2
        assert result.unanswered_count == 1


# ─── Timeline parsing tests ───

class TestParseTimeline:
    """Tests for parse_timeline() — parsing the Zoho CRM v8 Timeline API response."""

    def test_field_update_tracked(self):
        """Tracked field update is extracted."""
        timeline = {"__timeline": [{
            "action": "updated",
            "audited_time": "2026-02-08T10:00:00+01:00",
            "done_by": {"name": "System Bot"},
            "source": "crm_api",
            "field_history": [{
                "api_name": "Evalbox",
                "_value": {"old": "Pret a payer", "new": "Dossier Synchronisé"},
            }],
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(changes) == 1
        assert changes[0].field == 'Evalbox'
        assert changes[0].old_value == 'Pret a payer'
        assert changes[0].new_value == 'Dossier Synchronisé'
        assert changes[0].actor == 'System Bot'
        assert changes[0].source == 'crm_api'
        # API source → not a human intervention
        assert len(interventions) == 0

    def test_field_update_untracked_ignored(self):
        """Untracked field updates are ignored."""
        timeline = {"__timeline": [{
            "action": "updated",
            "audited_time": "2026-02-08T10:00:00+01:00",
            "done_by": {"name": "Bot"},
            "source": "crm_api",
            "field_history": [{
                "api_name": "SomeRandomField",
                "_value": {"old": "a", "new": "b"},
            }],
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(changes) == 0

    def test_human_field_update(self):
        """Field update via CRM UI is both a field change and human intervention."""
        timeline = {"__timeline": [{
            "action": "updated",
            "audited_time": "2026-02-08T10:00:00+01:00",
            "done_by": {"name": "Marwan"},
            "source": "crm_ui",
            "field_history": [{
                "api_name": "Session",
                "_value": {"old": "jour", "new": "soir"},
            }],
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(changes) == 1
        assert changes[0].field == 'Session'
        assert len(interventions) == 1
        assert interventions[0].actor == 'Marwan'
        assert interventions[0].action == 'field_updated'

    def test_note_added_human(self):
        """Note added via CRM UI is a human intervention."""
        timeline = {"__timeline": [{
            "action": "added",
            "audited_time": "2026-02-08T11:00:00+01:00",
            "done_by": {"name": "Lamia"},
            "source": "crm_ui",
            "record": {
                "module": {"api_name": "Notes"},
                "name": "Suivi candidat",
            },
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(changes) == 0
        assert len(interventions) == 1
        assert interventions[0].actor == 'Lamia'
        assert interventions[0].action == 'note_added'
        assert interventions[0].details == 'Suivi candidat'

    def test_note_added_by_api_not_human(self):
        """Note added via API is NOT a human intervention."""
        timeline = {"__timeline": [{
            "action": "added",
            "audited_time": "2026-02-08T11:00:00+01:00",
            "done_by": {"name": "Workflow Bot"},
            "source": "crm_api",
            "record": {
                "module": {"api_name": "Notes"},
                "name": "Auto note",
            },
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(interventions) == 0

    def test_email_sent_human(self):
        """Email sent manually is a human intervention."""
        timeline = {"__timeline": [{
            "action": "sent",
            "audited_time": "2026-02-08T12:00:00+01:00",
            "done_by": {"name": "Marwan"},
            "source": "crm_ui",
            "record": {"name": "Re: Votre inscription"},
        }]}
        changes, interventions = parse_timeline(timeline)
        assert len(interventions) == 1
        assert interventions[0].action == 'email_sent'
        assert interventions[0].actor == 'Marwan'

    def test_multiple_field_changes_sorted(self):
        """Multiple field changes are sorted by timestamp."""
        timeline = {"__timeline": [
            {
                "action": "updated",
                "audited_time": "2026-02-08T12:00:00+01:00",
                "done_by": {"name": "Bot"},
                "source": "crm_api",
                "field_history": [{"api_name": "Evalbox", "_value": {"old": "B", "new": "C"}}],
            },
            {
                "action": "updated",
                "audited_time": "2026-02-08T10:00:00+01:00",
                "done_by": {"name": "Bot"},
                "source": "crm_api",
                "field_history": [{"api_name": "Evalbox", "_value": {"old": "A", "new": "B"}}],
            },
        ]}
        changes, _ = parse_timeline(timeline)
        assert len(changes) == 2
        # Should be sorted oldest first
        assert changes[0].old_value == 'A'
        assert changes[1].old_value == 'B'

    def test_empty_timeline(self):
        changes, interventions = parse_timeline({})
        assert changes == []
        assert interventions == []

    def test_none_timeline(self):
        changes, interventions = parse_timeline(None)
        assert changes == []
        assert interventions == []

    def test_missing_timeline_key(self):
        changes, interventions = parse_timeline({"data": []})
        assert changes == []
        assert interventions == []

    def test_none_field_values(self):
        """Handle None values in field_history gracefully."""
        timeline = {"__timeline": [{
            "action": "updated",
            "audited_time": "2026-02-08T10:00:00+01:00",
            "done_by": {"name": "Bot"},
            "source": "crm_api",
            "field_history": [{
                "api_name": "Evalbox",
                "_value": {"old": None, "new": "Dossier créé"},
            }],
        }]}
        changes, _ = parse_timeline(timeline)
        assert len(changes) == 1
        assert changes[0].old_value == ''
        assert changes[0].new_value == 'Dossier créé'


# ─── Human intervention detection tests ───

class TestHumanIntervention:
    """Tests for _detect_human_intervention()."""

    def _make_meta(self, hours_ago):
        return MetaRecord(
            ticket_id='1',
            timestamp=datetime.now() - timedelta(hours=hours_ago),
            state='X',
            intent='A',
            evalbox='N/A',
            sections=['statut'],
        )

    def test_intervention_after_meta(self):
        """Human intervention after last META → detected."""
        last_meta = self._make_meta(hours_ago=24)
        interventions = [
            HumanIntervention(
                actor='Marwan',
                timestamp=datetime.now() - timedelta(hours=6),
                action='note_added',
                details='Suivi',
            ),
        ]
        result = _detect_human_intervention(interventions, last_meta)
        assert result['detected'] is True
        assert result['actor'] == 'Marwan'

    def test_intervention_before_meta(self):
        """Human intervention before last META → not detected."""
        last_meta = self._make_meta(hours_ago=6)
        interventions = [
            HumanIntervention(
                actor='Lamia',
                timestamp=datetime.now() - timedelta(hours=24),
                action='note_added',
                details='Old note',
            ),
        ]
        result = _detect_human_intervention(interventions, last_meta)
        assert result['detected'] is False

    def test_no_interventions(self):
        last_meta = self._make_meta(hours_ago=24)
        result = _detect_human_intervention([], last_meta)
        assert result['detected'] is False

    def test_no_last_meta(self):
        interventions = [
            HumanIntervention(
                actor='Marwan',
                timestamp=datetime.now(),
                action='email_sent',
            ),
        ]
        result = _detect_human_intervention(interventions, None)
        assert result['detected'] is False

    def test_meta_without_timestamp(self):
        last_meta = MetaRecord(ticket_id='1')
        interventions = [
            HumanIntervention(actor='X', timestamp=datetime.now(), action='note_added'),
        ]
        result = _detect_human_intervention(interventions, last_meta)
        assert result['detected'] is False


# ─── Timeline progression tests ───

class TestTimelineProgression:
    """Tests for progression detection via timeline field_changes."""

    def _make_notes(self, evalbox='N/A', date_exam='N/A'):
        ts = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
        content = f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox={evalbox} | date_exam={date_exam} | sections=statut"
        return {"data": [{"Note_Title": "Test", "Note_Content": content}]}

    def _make_timeline_with_evalbox_change(self, old_val, new_val, hours_ago=6):
        return {"__timeline": [{
            "action": "updated",
            "audited_time": (datetime.now() - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M:%S'),
            "done_by": {"name": "Bot"},
            "source": "crm_api",
            "field_history": [{
                "api_name": "Evalbox",
                "_value": {"old": old_val, "new": new_val},
            }],
        }]}

    def test_evalbox_progression_via_timeline(self):
        """Evalbox change detected via timeline field_changes."""
        notes = self._make_notes(evalbox='Pret a payer')
        deal = {'Evalbox': 'Dossier Synchronisé'}
        timeline = self._make_timeline_with_evalbox_change('Pret a payer', 'Dossier Synchronisé')
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=timeline)
        assert result.evalbox_changed is True
        assert result.evalbox_previous == 'Pret a payer'
        assert result.evalbox_current == 'Dossier Synchronisé'
        assert len(result.field_changes_since_last) >= 1

    def test_date_exam_change_via_timeline(self):
        """Date exam change detected via timeline."""
        notes = self._make_notes(date_exam='2026-03-31')
        deal = {'Evalbox': 'N/A', 'Date_examen_VTC': '34_2026-05-26'}
        timeline = {"__timeline": [{
            "action": "updated",
            "audited_time": (datetime.now() - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S'),
            "done_by": {"name": "Bot"},
            "source": "crm_api",
            "field_history": [{
                "api_name": "Date_examen_VTC",
                "_value": {"old": "34_2026-03-31", "new": "34_2026-05-26"},
            }],
        }]}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=timeline)
        assert result.date_exam_changed is True
        assert result.date_exam_previous == '2026-03-31'
        assert result.date_exam_current == '2026-05-26'

    def test_field_changes_filtered_by_meta_timestamp(self):
        """Only field changes AFTER the last META are included."""
        notes = self._make_notes(evalbox='Pret a payer')
        deal = {'Evalbox': 'Pret a payer'}
        # Field change BEFORE the META record (24h ago, META is 12h ago)
        timeline = self._make_timeline_with_evalbox_change('N/A', 'Pret a payer', hours_ago=24)
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=timeline)
        assert len(result.field_changes_since_last) == 0
        assert result.evalbox_changed is False


# ─── Human intervention resets suppression tests ───

class TestHumanInterventionResetsSuppression:
    """Tests that human intervention resets all suppression flags."""

    def _make_notes(self, sections, evalbox='N/A'):
        ts = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
        sections_str = ','.join(sections)
        content = f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox={evalbox} | sections={sections_str}"
        return {"data": [{"Note_Title": "T", "Note_Content": content}]}

    def _make_human_intervention_timeline(self, hours_ago=6):
        """Create a timeline with a human note added after META."""
        return {"__timeline": [{
            "action": "added",
            "audited_time": (datetime.now() - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M:%S'),
            "done_by": {"name": "Marwan"},
            "source": "crm_ui",
            "record": {
                "module": {"api_name": "Notes"},
                "name": "Suivi candidat",
            },
        }]}

    def test_suppression_reset_on_human_intervention(self):
        """When a human intervened after our last META, ALL suppressions are reset."""
        notes = self._make_notes(['identifiants', 'dates', 'sessions', 'statut', 'elearning', 'paiement'])
        deal = {'Evalbox': 'N/A'}
        timeline = self._make_human_intervention_timeline(hours_ago=6)
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=timeline)
        # All should be False despite sections being previously communicated
        assert result.suppress_identifiants is False
        assert result.suppress_dates is False
        assert result.suppress_sessions is False
        assert result.suppress_statut is False
        assert result.suppress_elearning is False
        assert result.suppress_paiement is False
        assert result.human_intervention_detected is True

    def test_suppression_intact_without_human_intervention(self):
        """Without human intervention, suppression works normally."""
        notes = self._make_notes(['identifiants', 'dates', 'sessions'])
        deal = {'Evalbox': 'N/A'}
        # No timeline → no human intervention
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=None)
        assert result.suppress_identifiants is True
        assert result.suppress_dates is True
        assert result.suppress_sessions is True
        assert result.human_intervention_detected is False

    def test_no_reset_if_intervention_before_meta(self):
        """Human intervention BEFORE META → no reset."""
        notes = self._make_notes(['identifiants', 'statut'])
        deal = {'Evalbox': 'N/A'}
        # Intervention 48h ago, META is 24h ago → intervention is before META
        timeline = self._make_human_intervention_timeline(hours_ago=48)
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=timeline)
        assert result.suppress_identifiants is True
        assert result.suppress_statut is True
        assert result.human_intervention_detected is False


# ─── Timeline graceful degradation tests ───

class TestTimelineGracefulDegradation:
    """Tests that timeline=None falls back to META-only behavior."""

    def _make_notes(self, evalbox='N/A'):
        ts = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
        content = f"[META] ticket=1 | ts={ts} | state=X | intent=A | evalbox={evalbox} | sections=statut"
        return {"data": [{"Note_Title": "T", "Note_Content": content}]}

    def test_timeline_none_works(self):
        """timeline=None → graceful fallback, no crash."""
        notes = self._make_notes(evalbox='Pret a payer')
        deal = {'Evalbox': 'Dossier Synchronisé'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline=None)
        assert result.has_history is True
        assert result.human_intervention_detected is False
        assert result.field_changes_since_last == []
        # Progression still works via META snapshot comparison
        assert result.evalbox_changed is True

    def test_empty_timeline_works(self):
        """Empty timeline dict → no changes, no interventions."""
        notes = self._make_notes()
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline={})
        assert result.human_intervention_detected is False
        assert result.field_changes_since_last == []

    def test_malformed_timeline_no_crash(self):
        """Malformed timeline data → graceful degradation."""
        notes = self._make_notes()
        deal = {'Evalbox': 'N/A'}
        result = analyze_thread_memory(notes, deal, 'SUIVI_DOSSIER', timeline={"__timeline": "not_a_list"})
        assert result.human_intervention_detected is False
        assert isinstance(result, ThreadMemoryResult)
