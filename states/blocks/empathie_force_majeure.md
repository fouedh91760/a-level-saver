<!-- BLOC: empathie_force_majeure -->
<!-- Format: HTML pour Zoho Desk -->
<!-- Affiche un message empathique adapté au type de force majeure -->

{{#if is_force_majeure_deces}}
<p>Nous sommes sincèrement désolés d'apprendre cette triste nouvelle. Toutes nos condoléances vous accompagnent dans cette période difficile.</p>
{{/if}}

{{#if is_force_majeure_medical}}
<p>Nous sommes désolés d'apprendre votre problème de santé. Nous espérons que vous vous rétablirez rapidement.</p>
{{/if}}

{{#if is_force_majeure_accident}}
<p>Nous sommes désolés d'apprendre cet accident. Nous espérons que tout se passera bien pour vous.</p>
{{/if}}
