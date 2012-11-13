({
	"nl" : {
		"question1"	: 'Wat is het rekenkundig gemiddelde van de volgende getallen?',
		"question2"	: 'Wat is de mediaan van de volgende getallen?',
		"question3"	: 'Wat is de modus van de volgende getallen?',
		
		"hint1"		: 'Om het gemiddelde te berekenen, tel je alle getallen bij elkaar op en deel je door het aantal getallen.',
		"hint2"		: 'Er zijn <code><var>INTEGERS_COUNT</var></code> getallen.',
		"hint3"		: 'Het gemiddelde is <code>\\displaystyle <var>fractionSimplification( sum(INTEGERS), INTEGERS_COUNT )</var></code>.',
		"hint4"		: 'Zet eerst de getallen op volgorde:',
		"hint5"		: 'Omdat er <code>2</code> getallen in het midden staan, is de mediaan het gemiddelde van <strong>die</strong> twee getallen!',
		"hint6"		: "De mediaan is het 'middelste' getal:",
		"hint7"		: 'De mediaan is <code>\\dfrac{<var>SORTED_INTS[ SORTED_INTS.length / 2 - 1 ]</var> + <var>SORTED_INTS[ SORTED_INTS.length / 2 ]</var>}{2}</code>.',
		"hint8"		: 'De mediaan is dus <code><var>fractionReduce(2 * MEDIAN, 2)</var></code>.',
		"hint9"		: 'Een andere manier om het middelste getal te vinden is door ze op een getallenlijn te tekenen. Als een getal meerdere keren voorkomt, tel dan alle bijbehorende stippen mee.',
		"hint10"	: 'De modus is het getal dat het vaakst voorkomt.',
		"hint11"	: 'Teken een histogram om te zien hoeveel keer elk nummer voorkomt.',
		"hint12"	: 'De <code><var>MODE</var></code> komt vaker voor dan elk ander getal, dus <code><var>MODE</var></code> is de modus.'
		}
})