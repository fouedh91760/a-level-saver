{{#if examen_passe}}
{{!-- CAS: Examen PASSÉ - vérifier délai 14 jours pour force majeure --}}
{{#if force_majeure_possible}}
{{#if mentions_force_majeure}}Votre demande de report est bien prise en compte. Pour que votre demande soit étudiée, merci de nous transmettre par email à <b>doc@cab-formations.fr</b> un justificatif :<br>
{{#if is_force_majeure_deces}}<ul><li>Le certificat ou avis de décès</li></ul>{{/if}}{{#if is_force_majeure_medical}}<ul><li>Un certificat médical attestant de votre impossibilité de vous présenter à l'examen</li></ul>{{/if}}{{#if is_force_majeure_accident}}<ul><li>Un document attestant de l'accident (certificat médical, constat, etc.)</li></ul>{{/if}}{{#if is_force_majeure_childcare}}<ul><li>Un justificatif de votre situation (indisponibilité de votre mode de garde, etc.)</li></ul>
<i>Conseil : pour maximiser vos chances d'acceptation, nous vous recommandons d'obtenir un certificat médical de votre médecin traitant. Ce type de justificatif est généralement mieux accepté par la CMA.</i><br>{{/if}}{{#if is_force_majeure_other}}<ul><li>Tout document justifiant votre impossibilité de vous présenter à l'examen</li></ul>
<i>Conseil : pour maximiser vos chances d'acceptation, nous vous recommandons d'obtenir un certificat médical de votre médecin traitant. Ce type de justificatif est généralement mieux accepté par la CMA.</i><br>{{/if}}
Dès réception, nous transmettrons votre demande à la CMA pour étude. <b>C'est la CMA qui statue sur l'acceptation ou le refus des demandes de report.</b> Nous vous tiendrons informé de leur décision. En cas de refus, des frais de réinscription de 241€ seront à prévoir.
{{else}}<b>Concernant votre demande de report :</b> vous avez été absent à l'examen du <b>{{date_examen}}</b>. Un report est encore possible avec un justificatif de force majeure :<br>
<ul><li>Certificat médical</li><li>Certificat de décès d'un proche</li><li>Tout document attestant de l'impossibilité de vous présenter</li></ul>
Pour demander un report, merci de nous transmettre votre justificatif par email à <b>doc@cab-formations.fr</b>. Nous soumettrons ensuite votre demande à la CMA. <b>Attention : cette demande doit être faite dans les 2 semaines suivant l'examen.</b> Sans justificatif valide, des frais de réinscription de 241€ seront à prévoir.
{{/if}}
{{else}}
{{!-- Examen passé depuis plus de 14 jours - force majeure impossible --}}
<b>Concernant votre demande de réinscription :</b><br><br>
Nous constatons que votre examen était prévu le <b>{{date_examen}}</b>, soit il y a plus de 2 semaines.<br><br>
Passé ce délai, un report pour force majeure n'est malheureusement <b>plus recevable</b> par la CMA. Pour repasser l'examen, une <b>nouvelle inscription</b> est nécessaire.<br><br>
{{#if uber_20}}<b>Information importante :</b> Dans le cadre de l'offre Uber, les frais de votre première inscription avaient été pris en charge par CAB Formations. Cette offre n'est valable qu'<b>une seule fois</b>.<br><br>{{/if}}<b>Deux options s'offrent à vous :</b><br><br>
<b>Option 1 - Inscription autonome (241€)</b><br>
Connectez-vous sur <a href="https://www.exament3p.fr">www.exament3p.fr</a>, sélectionnez une nouvelle date d'examen et procédez au paiement des frais d'inscription (241€).<br><br>
<b>Option 2 - Formation CPF (frais d'examen INCLUS)</b><br>
Vous pouvez utiliser votre <b>Compte Personnel de Formation (CPF)</b> pour financer une nouvelle formation VTC. Cette option présente de nombreux avantages :<br>
→ <b>Frais d'examen inclus</b> : les 241€ sont pris en charge, vous n'avez rien à avancer<br>
→ <b>Formation complète</b> : accès illimité à notre plateforme e-learning pour vous préparer sereinement<br>
→ <b>Accompagnement personnalisé</b> : un formateur dédié pour maximiser vos chances de réussite<br>
→ <b>Financé par vos droits CPF</b> : aucun frais de votre poche si vous avez suffisamment de droits<br><br>
{{#if is_female}}Intéressée{{else}}Intéressé{{/if}} ? Répondez simplement à ce mail en indiquant "<b>Je suis {{#if is_female}}intéressée{{else}}intéressé{{/if}} par la formation CPF</b>" et un conseiller vous rappellera pour vous présenter les offres disponibles.<br><br>
{{#if has_next_dates}}<b>Prochaines dates d'examen disponibles :</b><br>
{{#each next_dates}}&nbsp;&nbsp;→ <b>{{this.date_examen_formatted}}</b> (CMA {{this.Departement}}) - clôture le {{this.date_cloture_formatted}}<br>
{{/each}}{{/if}}
{{/if}}
{{else}}
{{!-- CAS: Examen FUTUR mais clôture passée - peut encore se présenter ou demander report avec justificatif --}}
<b>Concernant votre demande de report :</b><br><br>
Votre examen est prévu le <b>{{date_examen}}</b>. Malheureusement, la date limite de modification des inscriptions est maintenant passée.<br><br>
{{#if mentions_force_majeure}}<b>Demande de report pour force majeure :</b><br>
Pour que votre demande soit étudiée par la CMA, merci de nous transmettre un justificatif à <b>doc@cab-formations.fr</b> :<br>
<ul><li>Certificat médical</li><li>Certificat de décès d'un proche</li><li>Tout document attestant de l'impossibilité de vous présenter</li></ul>
<b>C'est la CMA qui statue sur l'acceptation ou le refus des demandes de report.</b> En cas de refus, des frais de réinscription de 241€ seront à prévoir.<br><br>
{{else}}<b>Vos options :</b><br><br>
<b>1. Vous présenter à l'examen</b><br>
Si vous êtes disponible le <b>{{date_examen}}</b>, nous vous encourageons à vous présenter. Vous recevrez votre convocation environ 10 jours avant l'examen.<br><br>
<b>2. Demander un report (avec justificatif)</b><br>
Si vous ne pouvez vraiment pas vous présenter, un report est possible uniquement avec un justificatif de force majeure (certificat médical, décès d'un proche, etc.). Envoyez votre justificatif à <b>doc@cab-formations.fr</b>.<br><br>
<b>3. Ne pas se présenter (absence)</b><br>
Si vous êtes absent sans justificatif valide, votre inscription sera perdue et des frais de réinscription de 241€ seront nécessaires pour une nouvelle date.<br>
{{#if uber_20}}<br><b>Rappel :</b> Dans le cadre de l'offre Uber, les frais de votre première inscription ont été pris en charge. Cette offre n'est valable qu'<b>une seule fois</b>.{{/if}}<br><br>
{{/if}}
{{#if has_next_dates}}<b>Prochaines dates d'examen disponibles (si report ou réinscription) :</b><br>
{{#each next_dates}}&nbsp;&nbsp;→ <b>{{this.date_examen_formatted}}</b> (CMA {{this.Departement}}) - clôture le {{this.date_cloture_formatted}}<br>
{{/each}}{{/if}}
{{/if}}
