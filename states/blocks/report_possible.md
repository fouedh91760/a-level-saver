<!-- BLOC: report_possible -->
<!-- Format: HTML pour Zoho Desk -->

<p>📅 <b>Concernant votre demande de report</b></p>

<p>Votre date d'examen actuelle est le {{date_examen}}. La date de clôture des inscriptions étant le {{date_cloture}}, un report est encore possible.</p>

<p><b>Prochaines dates disponibles :</b></p>

{{#each prochaines_dates}}
<p>
📅 {{this.date}} — Département {{this.departement}}<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Clôture des inscriptions : {{this.cloture}}
</p>
{{/each}}

<p>Merci de nous confirmer la nouvelle date souhaitée pour que nous puissions effectuer le changement.</p>

<p><i>Note : Un report entraîne également un changement de session de formation. Nous vous proposerons les nouvelles sessions disponibles une fois votre choix confirmé.</i></p>
