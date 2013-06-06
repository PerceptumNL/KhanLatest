({
	"nl" : {
		"question1"	: '<p>Sommige paren voor een lineaire functie van <span class='hint_orange'><code><var>X_VAR</var></code></span> zijn gegeven in onderstaande tabel.</p> <p><b>Welke vergelijking werd gebruikt voor het genereren van deze tabel?</b></p>',
		"question2"	: '<p>De data in de tabel hieronder geven de kosten van een doos groenten per gram weer, inclusief de kosten van de groenteboer om groenten te verpakken.</p> <p><b>Welke vergelijking past bij de data?</b></p>',
		"question3"	: '<p><b>De tabel hieronder is ontstaan door de volgende vergelijking te gebruiken:</b><code>\quad f(x) = <var>COEF</var>x + <var>CONST</var></code></p> <p><b>Vind de ontbrekende waarden.</b></p>',

		"var1"		: '"p"',
		"var2"		: '"c"',
		"var3"		: '"Gram (g)"',
		"var4"		: '"Kosten (k)"',
		
		"hint0"		: 'Neem 1 van de vergelijkingen en probeer deze aan te sluiten in de waarden uit de tabel. Als de gelijkheid niet voor ten minste één set waarden overeenkomt, kunnen we dat antwoord schrappen.',
		"hint1"		: 'Bijvoorbeeld, overweeg  <code><var>Y_VAR</var> = <var>WRONG_ANSWERS[0].coef</var><var>X_VAR</var> + <var>WRONG_ANSWERS[0].const</var></code>. Vervanging van <code>\color{<var>ORANGE</var>}{<var>X_VAR</var> = <var>XVALS[0]</var>}</code> en <code>\color{<var>BLUE</var>}{<var>Y_VAR</var> = <var>XVALS[0] * COEF + CONST</var>}</code> blijkt dat de gelijkheid voor de eerste rij van de tabel geldt :',
		"hint2"		: 'Maar invullen van <code>\color{<var>ORANGE</var>}{<var>X_VAR</var> = <var>XVALS[1]</var>}</code> en <code>\color{<var>BLUE</var>}{<var>Y_VAR</var> = <var>XVALS[1] * COEF + CONST</var>}</code> uit de tweede regel van de tabel geeft:',
		"hint3"		: 'Dus kunnen we <code><var>Y_VAR</var> = <var>WRONG_ANSWERS[0].coef</var><var>X_VAR</var> + <var>WRONG_ANSWERS[0].const</var></code> uit de oplossingen schrappen en een ander antwoord proberen.',
		"hint4"		: 'Als we <code><var>Y_VAR</var> = <var>COEF</var><var>X_VAR</var> + <var>CONST</var></code> proberen, dan zien we dat het juist is voor elke set getallen uit de tabel.',
		"hint5"		: 'De juiste vergelijking voor de waarden uit deze tabel is <code><var>Y_VAR</var> = <var>COEF</var><var>X_VAR</var> + <var>CONST</var></code>.',
		"hint6"		: 'Zet de waarden van <code class="hint_orange">x</code> in de vergelijking om de ontbrekende waarden van <code class="hint_blue">f(x)</code>.',
		"hint7"		: '<span data-if="I === 1">Het ontbrekende getal is</span><span data-else>De ontbrekende getallen zijn</span>:'
		}
})
