({
	"nl" : {
		"question1"	: '<var>person(1)</var> heeft vandaag <var>YEAR_PERCENT_MORE</var>% meer geld dan vorig jaar rond deze tijd. Als <var>person(1)</var> vandaag €<var>YEAR_THIS</var> heeft, hoeveel geld heeft <var>he(1)</var> dan dit afgelopen jaar verdiend? (Rond af op de cent nauwkeurig, of, in andere woorden, op een honderste van een euro.)',
		"question2"	: '<var>person(1)</var> heeft €<var>DOLLARS</var> om te besteden in een winkel. De winkel heeft momenteel een uitverkoop met uitverkoopprijzen die <var>PERCENT_OFF</var>% lager zijn dan de oorspronkelijke prijzen. Wat is de hoogste oorspronkele verkoopprijs die <var>person(1)</var> zich kan veroorloven? (Rond af op de cent nauwkeurig, of ,in andere woorden, op een honderste van een euro.)',
	
		"hint1"		: 'Laat <code>x</code> de hoeveelheid geld zijn dat <var>he(1)</var> vorig jaar had.',
		"hint2"		: '<code>x = €<var>YEAR_LAST</var></code> (afgerond op de cent nauwkeurig)',
		"hint3"		: '<var>He(1)</var> had vorig jaar dus €<var>YEAR_LAST</var>, maar we willen weten hoeveel <var>he(1)</var> verdiend heeft <b>het afgelopen jaar!</b>',
		"hint4"		: 'Hoeveelheid verdiend geld afgelopen jaar = hoeveelheid geld vandaag - hoeveelheid geld afelopen jaar',
		"hint5"		: 'Dus, het antwoord is €<var>round((YEAR_THIS - YEAR_LAST) * 100) / 100</var>.',
		"hint6"		: 'Laten we de hoogste oorspronkelijke prijs die <var>person(1)</var> zich kan veroorloven <code>x</code> noemen.',
		"hint7"		: '<code>x-<var>(PERCENT_OFF/100)</var>x = \\text{uitverkoopprijs} = \\text{bedrag dat <var>person( 1 )</var> kan besteden}</code>'
		}
})