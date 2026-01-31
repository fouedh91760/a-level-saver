💳 <b>Statut de votre dossier</b><br>
{{#if deadline_passed_reschedule}}
Vos documents ont bien été transmis à la CMA. Votre dossier est en attente de paiement.<br>
N° de dossier : {{num_dossier}}<br><br>
⚠️ <b>Information importante :</b> Les inscriptions pour l'examen du {{date_examen}} sont maintenant clôturées (date limite : {{date_cloture}}).<br>
{{#if new_exam_date}}
Votre inscription sera effectuée sur la prochaine session : <b>{{new_exam_date}}</b>{{#if new_exam_date_cloture}} (clôture : {{new_exam_date_cloture}}){{/if}}.<br>
{{/if}}
{{else}}
Vos documents ont bien été transmis à la CMA. Votre dossier est en attente de paiement des frais d'inscription.<br>
N° de dossier : {{num_dossier}}<br>
Date d'examen prévue : {{date_examen}}<br>
Date limite d'inscription : {{date_cloture}}<br>
{{/if}}
