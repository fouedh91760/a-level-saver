<!-- BLOC: statut_refus_cma -->
<!-- Données: {{documents_refuses}} -->
<!-- Format: HTML pour Zoho Desk -->

<p>⚠️ <b>Pièce(s) à corriger</b></p>

<p>La CMA a relevé un problème avec certains documents de votre dossier. Voici le détail :</p>

{{#each documents_refuses}}
<p>
<b>{{this.nom}}</b><br>
→ Motif du refus : {{this.motif}}
{{#if this.conseil}}<br>→ Notre conseil : {{this.conseil}}{{/if}}
</p>
{{/each}}

<p><b>Ce que vous devez faire :</b></p>

<ol>
<li>Connectez-vous sur <a href="https://www.exament3p.fr">ExamT3P</a> avec vos identifiants</li>
<li>Accédez à la section "Mes documents"</li>
<li>Supprimez le document refusé</li>
<li>Téléchargez le nouveau document conforme</li>
</ol>

<p><b>Date limite :</b> Vous devez corriger avant le {{date_cloture}} pour conserver votre date d'examen du {{date_examen}}.</p>
