<!-- BLOC: rappel_formation_imminente -->
<!-- Condition: session_choisie existe ET date_debut proche -->
<!-- Format: HTML pour Zoho Desk -->

<p><b>Rappel : Votre formation approche !</b></p>

<p>Votre session de formation commence le <b>{{session_date_debut}}</b>.</p>

<p><b>À faire avant le début :</b></p>
<ul>
<li>Complétez les modules e-learning sur votre <a href="https://cab-formations.fr/user">espace e-learning</a></li>
<li>Préparez vos questions pour les formateurs</li>
<li>Vérifiez que vous êtes bien disponible aux dates prévues</li>
</ul>

{{#if session_format_visio}}
<p><i>Vous recevrez le lien Zoom par email la veille du premier jour.</i></p>
{{/if}}
