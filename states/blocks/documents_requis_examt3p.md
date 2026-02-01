{{!-- Bloc: Documents requis ExamT3P --}}
{{!-- Ne s'affiche que si le candidat gère lui-même (EXAM_INCLUS = Non) --}}
{{#unless cab_paye_examen}}
<b>Documents requis pour votre inscription</b><br>Voici les documents que vous devez fournir sur <a href="https://www.exament3p.fr">ExamT3P</a> :<br>
{{> partials/common/liste_documents_requis}}
<i>Conseil : Vérifiez que vos scans sont lisibles et que les quatre coins du document sont visibles.</i><br>
{{/unless}}
