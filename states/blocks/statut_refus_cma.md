⚠️ <b>Pièce(s) à corriger</b><br>La CMA a relevé un problème avec certains documents de votre dossier. Voici le détail :<br>{{#each documents_refuses}}
<b>{{this.nom}}</b><br>→ Motif du refus : {{this.motif}}
{{#if this.conseil}}<br>→ Notre conseil : {{this.conseil}}{{/if}}
<br>{{/each}}
<b>Ce que vous devez faire :</b><br><ol>
<li>Connectez-vous sur <a href="https://www.exament3p.fr">ExamT3P</a> avec vos identifiants</li>
<li>Accédez à la section "Mes documents"</li>
<li>Supprimez le document refusé</li>
<li>Téléchargez le nouveau document conforme</li>
</ol>
<b>Date limite :</b> Vous devez corriger avant le {{date_cloture}} pour conserver votre date d'examen du {{date_examen}}.<br>
