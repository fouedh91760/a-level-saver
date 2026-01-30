{{#if force_majeure_possible}}{{#if mentions_force_majeure}}Votre demande de report est bien prise en compte. Pour que votre demande soit étudiée, merci de nous transmettre par email à <b>doc@cab-formations.fr</b> un justificatif :<br>
{{#if is_force_majeure_deces}}<ul><li>Le certificat ou avis de décès</li></ul>{{/if}}{{#if is_force_majeure_medical}}<ul><li>Un certificat médical attestant de votre impossibilité de vous présenter à l'examen</li></ul>{{/if}}{{#if is_force_majeure_accident}}<ul><li>Un document attestant de l'accident (certificat médical, constat, etc.)</li></ul>{{/if}}{{#if is_force_majeure_childcare}}<ul><li>Un justificatif de votre situation (indisponibilité de votre mode de garde, etc.)</li></ul>
<i>Conseil : pour maximiser vos chances d'acceptation, nous vous recommandons d'obtenir un certificat médical de votre médecin traitant. Ce type de justificatif est généralement mieux accepté par la CMA.</i><br>{{/if}}{{#if is_force_majeure_other}}<ul><li>Tout document justifiant votre impossibilité de vous présenter à l'examen</li></ul>
<i>Conseil : pour maximiser vos chances d'acceptation, nous vous recommandons d'obtenir un certificat médical de votre médecin traitant. Ce type de justificatif est généralement mieux accepté par la CMA.</i><br>{{/if}}
Dès réception, nous transmettrons votre demande à la CMA pour étude. <b>C'est la CMA qui statue sur l'acceptation ou le refus des demandes de report.</b> Nous vous tiendrons informé(e) de leur décision. En cas de refus, des frais de réinscription de 241€ seront à prévoir.{{else}}<b>Concernant votre demande de report :</b> votre inscription à l'examen VTC a été validée par la CMA et les inscriptions sont maintenant clôturées. Un report n'est possible qu'avec un justificatif de force majeure :<br>
<ul><li>Certificat médical</li><li>Certificat de décès d'un proche</li><li>Tout document attestant de l'impossibilité de vous présenter</li></ul>
Pour demander un report, merci de nous transmettre votre justificatif par email à <b>doc@cab-formations.fr</b>. Nous soumettrons ensuite votre demande à la CMA. Sans justificatif valide, des frais de réinscription de 241€ seront à prévoir.{{/if}}{{else}}<b>Concernant votre demande de report/réinscription :</b><br><br>
Nous constatons que votre examen était prévu le <b>{{date_examen}}</b>, soit il y a plus de 2 semaines.<br><br>
Passé ce délai, un report pour force majeure n'est malheureusement <b>plus recevable</b> par la CMA. Pour repasser l'examen, une <b>nouvelle inscription</b> est nécessaire.<br><br>
{{#if uber_20}}<b>Information importante :</b> Dans le cadre de l'offre Uber, les frais de votre première inscription avaient été pris en charge par CAB Formations. Cette offre n'est valable qu'<b>une seule fois</b>.<br><br>{{/if}}<b>Deux options s'offrent à vous :</b><br><br>
<b>Option 1 - Inscription autonome (241€)</b><br>
<ol>
<li>Connectez-vous sur <a href="https://www.exament3p.fr">www.exament3p.fr</a></li>
<li>Sélectionnez une nouvelle date d'examen</li>
<li>Procédez au paiement des frais d'inscription (241€)</li>
</ol>
<b>Option 2 - Formation CPF (frais d'examen INCLUS)</b><br>
Saviez-vous que vous pouvez utiliser votre <b>Compte Personnel de Formation (CPF)</b> pour financer une nouvelle formation VTC ? Cette option présente de nombreux avantages :<br>
<ul>
<li><b>Frais d'examen inclus</b> : les 241€ sont pris en charge, vous n'avez rien à avancer</li>
<li><b>Formation complète</b> : accès illimité à notre plateforme e-learning pour vous préparer sereinement</li>
<li><b>Accompagnement personnalisé</b> : un formateur dédié pour maximiser vos chances de réussite</li>
<li><b>Financé par vos droits CPF</b> : aucun frais de votre poche si vous avez suffisamment de droits</li>
</ul>
<b>Intéressé(e) ?</b> Répondez simplement à ce mail et nous transmettrons votre dossier à l'un de nos conseillers formation qui vous contactera rapidement pour vous présenter les offres disponibles et vérifier vos droits CPF.<br><br>
{{#if has_next_dates}}<b>Prochaines dates d'examen disponibles :</b><br>
{{#each next_dates}}&nbsp;&nbsp;→ <b>{{this.date_examen_formatted}}</b> (CMA {{this.Departement}}) - clôture le {{this.date_cloture_formatted}}<br>
{{/each}}<br>{{/if}}{{/if}}
