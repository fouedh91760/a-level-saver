<!-- BLOC: prochaines_dates_examen -->
<!-- Données: {{prochaines_dates}} -->
<!-- Format: HTML pour Zoho Desk -->

<p><b>Prochaines dates d'examen disponibles</b></p>

{{#each prochaines_dates}}
<p>
📅 <b>{{this.date}}</b> — Département {{this.departement}}<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Clôture des inscriptions : {{this.cloture}}
</p>
{{/each}}

<p>Merci de nous indiquer la date qui vous convient le mieux afin que nous puissions procéder à votre inscription.</p>
