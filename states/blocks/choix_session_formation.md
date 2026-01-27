<!-- BLOC: choix_session_formation -->
<!-- Format: HTML pour Zoho Desk -->

<p><b>Choisissez votre session de formation</b></p>

<p>Voici les prochaines sessions disponibles :</p>

{{#each sessions_proposees}}
<p>
<b>{{this.nom}}</b><br>
→ Dates : du {{this.date_debut}} au {{this.date_fin}}<br>
→ Horaires : {{this.horaires}}<br>
→ Format : {{this.format}}<br>
→ Places disponibles : {{this.places_restantes}}
</p>
{{/each}}

<p>Merci de nous indiquer la session qui vous convient le mieux.</p>
