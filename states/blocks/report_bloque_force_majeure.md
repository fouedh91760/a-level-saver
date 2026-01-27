<!-- BLOC: report_bloque_force_majeure -->
<!-- Format: HTML pour Zoho Desk -->
<!-- S'adapte si force majeure déjà mentionnée par le candidat -->

{{#if mentions_force_majeure}}
<p>Votre demande de report est bien prise en compte.</p>

<p>Votre situation constitue un cas de force majeure. Pour finaliser votre demande, merci de nous transmettre par email à <b>doc@cab-formations.fr</b> :</p>

{{#if is_force_majeure_deces}}
<ul>
<li>Le certificat ou avis de décès</li>
</ul>
{{/if}}

{{#if is_force_majeure_medical}}
<ul>
<li>Un certificat médical attestant de votre impossibilité de vous présenter à l'examen</li>
</ul>
{{/if}}

{{#if is_force_majeure_accident}}
<ul>
<li>Un document attestant de l'accident (certificat médical, constat, etc.)</li>
</ul>
{{/if}}

<p>Dès réception de ce document, nous soumettrons votre demande à la CMA et vous proposerons une nouvelle date d'examen.</p>

{{else}}
<p>⚠️ <b>Concernant votre demande de report</b></p>

<p>Votre inscription à l'examen VTC a été validée par la CMA et les inscriptions sont maintenant clôturées.</p>

<p>Un report n'est possible qu'avec un justificatif de force majeure :</p>
<ul>
<li>Certificat médical</li>
<li>Certificat de décès d'un proche</li>
<li>Tout document attestant de l'impossibilité de vous présenter</li>
</ul>

<p><b>Pour demander un report</b>, merci de nous transmettre votre justificatif par email à <b>doc@cab-formations.fr</b>.</p>

<p>Nous soumettrons ensuite votre demande à la CMA pour validation et vous proposerons une nouvelle date.</p>

<p><i>Sans justificatif valide, des frais de réinscription de 241€ seront à prévoir.</i></p>
{{/if}}
