<b>Sessions de formation disponibles</b><br>Pour préparer votre examen du {{date_examen}}, voici les sessions que nous vous proposons :<br>{{#each sessions_proposees}}
{{#if (eq this.type "jour")}}☀️ <b>Cours du jour</b>{{else}}🌙 <b>Cours du soir</b>{{/if}}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Du {{this.debut}} au {{this.fin}}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Horaires : {{this.horaires}}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{{#if (eq this.type "jour")}}Durée : 1 semaine{{else}}Durée : 2 semaines{{/if}}
<br>{{/each}}
Merci de nous confirmer votre préférence pour que nous puissions finaliser votre inscription.<br>
