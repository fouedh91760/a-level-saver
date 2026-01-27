<!-- BLOC: changement_departement -->
<!-- Condition: compte_existe == false -->
<!-- Format: HTML pour Zoho Desk -->

<p><b>Changement de département d'examen</b></p>

<p>Vous n'avez pas encore de compte ExamT3P, ce qui signifie que vous pouvez vous inscrire dans le département de votre choix.</p>

<p>Voici quelques options avec des dates plus proches :</p>

{{#each dates_autres_departements}}
<p>
→ <b>{{this.departement_nom}}</b> : {{this.date_examen}} (clôture le {{this.date_cloture}})
</p>
{{/each}}

<p>Souhaitez-vous que nous créions votre compte dans un autre département ?</p>
