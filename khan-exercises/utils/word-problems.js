// Example usage:
// <var>person(1)</var> traveled 5 mi by <var>vehicle(1)</var>. Let
// <var>his(1)</var> average speed be <var>personVar(1)</var>.
// Let <var>person(2)</var>'s speed be <var>personVar(2)</var>.
//
// Note that initials (-Var) are guaranteed to be unique in each category,
// but not across them.

jQuery.extend( KhanUtil, {
	toSentence: function( array, conjunction ) {
		if ( conjunction == null ) {
			conjunction = "en";
		}

		if ( array.length === 0 ) {
			return "";
		} else if ( array.length === 1 ) {
			return array[0];
		} else if ( array.length === 2 ) {
			return array[0] + " " + conjunction + " " + array[1];
		} else {
			return array.slice(0, -1).join(", ") + ", " + conjunction + " " + array[ array.length - 1 ];
		}
	},

	toSentenceTex: function( array, conjunction, highlight, highlightClass ) {
		var wrapped = jQuery.map( array, function( elem ) {
			if ( ( jQuery.isFunction( highlight ) && highlight( elem ) ) || ( highlight !== undefined && elem === highlight ) ) {
				return "<code class='" + highlightClass + "'>" + elem + "</code>";
			}
			return "<code>" + elem + "</code>";
		});
		return KhanUtil.toSentence( wrapped, conjunction );
	},

	// pluralization helper.  There are five signatures
	// - plural(NUMBER): return "s" if NUMBER is not 1
	// - plural(NUMBER, singular):
	//		- if necessary, magically pluralize <singular>
	//		- return "NUMBER word"
	// - plural(NUMBER, singular, plural): bijvoorbeeld plural (x, "paard","paarden") Als X=1: 1 paard, als x=5 5 paarden
	//		- return "NUMBER word"
	// - plural(singular, NUMBER):
	//		- if necessary, magically pluralize <singular>
	//		- return "word"
	// - plural(singular, plural, NUMBER): bijvoorbeeld plural ("paard","paarden",x) Als X=1: paard, als x=5: paarden
	//		- return "word"
	plural: (function() {
		var oneOffs = {
			'quiz': 'quizzes',
			'plank': 'planken',
			'rij': 'rijen',
			'map': 'mappen',
			'druif': 'druiven',
			'rok': 'rokken',
			'is': 'zijn',
			'was': 'waren',
			'tomaat': 'tomaten',
			'banaan':'bananen',
			'kokosnoot':'kokosnoten',
			'zeehond': 'zeehonden',
			'kiwi':'kiwi\'s',
			'citroen':'citroenen',
			'mango':'mango\'s',
			'watermeloen':'watermeloenen',
			'boon':'bonen',
			'pen':'pennen',
			'aap':'apen',
			'hond':'honden',
			'jaar':'jaren',
			'stift': 'stiften',
			'potlood':'potloden',
			'schrift':'schriften',
			'tas': 'tassen',
			'zaag':'zagen',
			'brood':'broden',
			'gorilla': 'gorilla\'s',
			'pak melk':'pakken melk',
			'lijmstift': 'lijmstiften',
			'knuffelbeer':'knuffelberen',
			'toets': 'toetsen',
			'narcis': 'narcissen',
			'pop':'poppen',
			'taart':'taarten',
			'trainingsbroek': 'trainingsbroeken',
			'pizza':'pizza\'s',
			'persoon':'personen',
			'zebra': 'zebra\'s',
			'beer': 'beren',
			'les': 'lessen',
			'auto':'auto\'s',
			'boom':'bomen',
			'hoed': 'hoeden',
			'hele getal':'hele getallen',
			'tiental':'tientallen',
			'leeuw': 'leeuwen',
			'honderdtal':'honderdtallen',
			'duizendtal':'duizendtallen',
			'wortel': 'wortelen',
			'tussentoets': 'tussentoetsen',
			'broek':'broeken',
			'slang': 'slangen',
			'tulp': 'tulpen',
			'roos': 'rozen',
			'fruit': 'fruit',
			'gunstige uitkomst': 'gunstige uitkomsten',
			'riem':'riemen',
			'ketting':'kettingen',
			'stropdas':'stropdassen',
			'trui':'truien',
			'kleur': 'kleuren',
			'krokodil': 'krokodillen',
			'sjaal': 'sjalen',
			'jas':'jassen',
			'jurk': 'jurken',
			'boek': 'boeken',
			'schildpad': 'schildpadden',
			'stoel': 'stoelen',
			'blik soep': 'blikken soep',
			'maiskolf': 'maiskolven',
			'rij': 'rijen',
			'zak': 'zakken',
			'olifant': 'olifanten',
			'leerling': 'leerlingen',
			'stip': 'stippen',
			'leerkracht': 'leerkrachten',
			'plank': 'planken',
			'hagedis': 'hagedissen',
			'dierentuin': 'dierentuinen',
			'supermarkt': 'supermarkten',
			'doos': 'dozen',
			'euro': 'euro', 
			'lange afstand renner': 'lange afstand renners',
			'keer':'keer'
		};

		var pluralizeWord = function(word) {

			// noone really needs extra spaces at the edges, do they?
			word = jQuery.trim( word );

			// determine if our word is all caps.  If so, we'll need to
			// re-capitalize at the end
			var isUpperCase = (word.toUpperCase() === word);
			var oneOff = oneOffs[word.toLowerCase()];
			var words = word.split(/\s+/);

			// first handle simple one-offs
			// ({}).watch is a function in Firefox, blargh
			if ( typeof oneOff === "string" ) {
				return oneOff;
			}

			// multiple words
			else if ( words.length > 1 ) {
				// for 3-word phrases where the middle word is 'in' or 'of',
				// pluralize the first word
				if ( words.length === 3 && /\b(in|of)\b/i.test(words[1]) ) {
					words[0] = KhanUtil.plural( words[0] );
				}

				// otherwise, just pluraize the last word
				else {
					words[ words.length-1 ] =
						KhanUtil.plural( words[ words.length-1 ] );
				}

				return words.join(" ");
			}

			// single words
			else {
				// "-y" => "-ies"
				if ( /[^aeiou]y$/i.test( word ) ) {
					word = word.replace(/y$/i, "ies");
				}

				// add "es"; things like "fish" => "fishes"
				else if ( /[sxz]$/i.test( word ) || /[bcfhjlmnqsvwxyz]h$/.test( word ) ) {
					word += "es";
				}

				// all the rest, just add "s"
				else {
					word += "s";
				}

				if ( isUpperCase ) {
					word = word.toUpperCase();
				}
				return word;
			}
		};

		return function(value, arg1, arg2) {
			if ( typeof value === "number" ) {
				var usePlural = (value !== 1);

				// if no extra args, just add "s" (if plural)
				if ( arguments.length === 1 ) {
					return usePlural ? "s" : "";
				}

				if ( usePlural ) {
					arg1 = arg2 || pluralizeWord(arg1);
				}

				return value + " " + arg1;
			} else if ( typeof value === "string" ) {
				var plural = pluralizeWord(value);
				if ( typeof arg1 === "string" && arguments.length === 3 ) {
					plural = arg1;
					arg1 = arg2;
				}
				var usePlural = (arguments.length < 2 || (typeof arg1 === "number" && arg1 !== 1));
				return usePlural ? plural : value;
			}
		};
	})()
});

jQuery.fn[ "word-problemsLoad" ] = function() {
	var people = KhanUtil.shuffle([
		["Yvonne", "f"],
		["Arco", "m"],
		["Philipp", "m"],
		["Ronald", "m"],
		["Britta", "f"],
		["Pauline", "f"],
		["Josh", "m"],
		["Jessica", "f"],
		["Tjalle", "m"],
		["Diederik", "m"],
		["Julius", "m"],
		["Frum", "f"],
		["Dennis", "m"],
		["Els", "f"],
		["Maud", "f"],
		["Bambi", "f"],
		["Hanneke", "f"],
		["Levi", "m"]
	]);

	var vehicles = KhanUtil.shuffle([
		"fiets",
		"auto",
		"tram",
		"motor",
		"scooter",
		"trein",
		"bus"
	]);

	var courses = KhanUtil.shuffle([
		"wiskunde",
		"scheikunde",
		"geschiedenis",
		"aardrijkskunde",
		"Engelse",
		"Biologie"
	]);

	var lessen = KhanUtil.shuffle([
		"wiskunde",
		"scheikunde",
		"geschiedenis",
		"aardrijkskunde",
		"Engels",
		"Biologie"
	]);

	var exams = KhanUtil.shuffle([
		"tussentoets",
		"toets",
		"quiz"
	]);

	var binops = KhanUtil.shuffle([
		"\\barwedge",
		"\\veebar",
		"\\odot",
		"\\oplus",
		"\\otimes",
		"\\oslash",
		"\\circledcirc",
		"\\boxdot",
		"\\bigtriangleup",
		"\\bigtriangledown",
		"\\dagger",
		"\\diamond",
		"\\star",
		"\\triangleleft",
		"\\triangleright"
	]);

	var collections = KhanUtil.shuffle([
		["stoel", "rij", "maakt"],
		["snoepje", "zak", "vult"],
		["koekje", "stapel", "maakt"],
		["boek", "plank", "vult",],
		["blik soep", "doos", "vult",]
	]);

	var stores = KhanUtil.shuffle([
		{
			name: "kantoorboekhandel",
			items: KhanUtil.shuffle( ["pen", "potlood", "schrift"] )
		},
		{
			name: "gereedschapswinkel",
			items: KhanUtil.shuffle( ["hamer", "spijker", "zaag"] )
		},
		{
			name: "supermarkt",
			items: KhanUtil.shuffle( ["banaan", "brood", "pak melk", "aardappel"] )
		},
		{
			name: "cadeauwinkel",
			items: KhanUtil.shuffle( ["spelletje", "game", "souvenir"] )
		},
		{
			name: "speelgoedwinkel",
			items: KhanUtil.shuffle( ["knuffelbeer", "videospelletje", "autootje", "pop"] )
		}
	]);

	var pizzas = KhanUtil.shuffle([
		"pizza",
		"taart",
		"cake"
	]);

	var timesofday = KhanUtil.shuffle([
		"in de ochtend",
		"in de middag",
		"\'s avonds"
	]);

	var exercises = KhanUtil.shuffle([
		"push-up",
		"sit-up"
	]);

	var fruits = KhanUtil.shuffle([
		"appel",
		"banaan",
		"kokosnoot",
		"kiwi",
		"citroen",
		"mango",
		"nectarine",
		"sinaasappel",
		"watermeloen",
		"druif"
	]);


	var deskItems = KhanUtil.shuffle([
		"schrift",
		"krijtje",
		"gummetje",
		"map",
		"lijmstift",
		"stift",
		"notitieboekje",
		"pen",
		"potlood"
	]);

	var colors = KhanUtil.shuffle([
		"rode",
		"oranje",
		"gele",
		"groene",
		"blauwe",
		"paarse",
		"witte",
		"zwarte",
		"bruine",
		"zilveren",
		"gouden",
		"roze"
	]);

	var kleuren = KhanUtil.shuffle([
		"rood",
		"oranje",
		"geel",
		"groen",
		"blauw",
		"paars",
		"wit",
		"zwart",
		"bruin",
		"zilver",
		"goud",
		"roze"
	]); 

	var schools = KhanUtil.shuffle([
		"de Noordwijkse school",
		"de Emmaschool",
		"de Almondschool",
		"de Covington school",
		"de Springer",
		"de Santa Rita school",
		"het Twents Carmel College",
		"de Oak school"
	]);

	var dieren = KhanUtil.shuffle([
		"leeuw",
		"tijger",
		"nijlpaard",
		"stekelvarken",
		"aap",
		"hond",
		"olifant",
	]); 

	var clothes = KhanUtil.shuffle([
		"hoed",
		"broek",
		"riem",
		"ketting",
		"tas",
		"rok",
		"trainingsbroek",
		"trui",
		"sweater",
		"stropdas",
		"sjaal",
		"jurk",
		"jas"
	]);

	var sides = KhanUtil.shuffle([
		"linker",
		"rechter"
	]);

	var shirtStyles = KhanUtil.shuffle([
		"lange mouwen",
		"korte mouwen"
	]);

	// animal, avg-lifespan, stddev-lifespan
	// (data is from cursory google searches and wild guessing)
	var animals = KhanUtil.shuffle([
		[ "krokodil", 68, 20 ],
		[ "miereneter", 15, 10 ],
		[ "beer", 40, 20],
		[ "olifant", 60, 10 ],
		[ "gorilla", 20, 5 ],
		[ "leeuw", 12, 5 ],
		[ "hagedis", 3, 1 ],
		[ "stokstaartje", 13, 5 ],
		[ "stekelvarken", 20, 5 ],
		[ "zeehond", 15, 10 ],
		[ "luiaard", 16, 5 ],
		[ "slang", 25, 10 ],
		[ "tijger", 22, 5 ],
		[ "schildpad", 100, 20 ],
		[ "zebra", 25, 10 ]
	]);

	var farmers = KhanUtil.shuffle([
		{farmer:"tuinder", crops:KhanUtil.shuffle(["tomaat", "aardappel", "wortel", "boon", "maiskolf"]), fieldss: "het veld", field:"veld"},
		{farmer:"kweker", crops:KhanUtil.shuffle(["roos", "tulp", "narcis", "sneeuwklokje", "lelie"]), fieldss: "de kas", field:"kas"}
	]);

	var distances = KhanUtil.shuffle([
		"kilometer"
	]);

	var distanceActivities = KhanUtil.shuffle([
		{present:"rijdt", past:"reed", noun:"fiets", voltooiddeelwoord: "gefietst",werkwoorden: "fietsen", done:"heeft gefietst", voorzetsel: "op", continuous:"aan het fietsen"},
		{present:"roeit", past:"roeide", noun:"boot", voltooiddeelwoord: "geroeid",werkwoorden: "roeien", done:"heeft geroeid", voorzetsel: "in", continuous:"aan het roeien"},
		{present:"rijdt", past:"reed", noun:"auto", voltooiddeelwoord: "gereden", werkwoorden: "auto rijden", done:"heeft gereden", voorzetsel: "in", continuous:"aan het rijden"},
		{present:"loopt", past:"liep", noun:"hond", voltooiddeelwoord: "gelopen", werkwoorden: "lopen", done:"heeft gelopen", voorzetsel: "met", continuous:"aan het lopen"}
	]);

	var indefiniteArticle = function(word) {
		var vowels = ['a', 'e', 'i', 'o', 'u'];
		if ( _(vowels).indexOf( word[0].toLowerCase() ) > -1 ) {
			return 'An ' + word;
		}
		return 'A ' + word;
	};

	jQuery.extend( KhanUtil, {
		person: function( i ) {
			return people[i - 1][0];
		},

		personVar: function( i ) {
			return people[i - 1][0].charAt(0).toLowerCase();
		},

		he: function( i ) {
			return people[i - 1][1] === "m" ? "hij" : "zij";
		},

		He: function( i ) {
			return people[i - 1][1] === "m" ? "Hij" : "Zij";
		},

		him: function( i ) {
			return people[i - 1][1] === "m" ? "hem" : "haar";
		},

		his: function( i ) {
			return people[i - 1][1] === "m" ? "zijn" : "haar";
		},

		His: function( i ) {
			return people[i - 1][1] === "m" ? "Zijn" : "Haar";
		},


		An: function(word) {
			return indefiniteArticle(word);
		},

		an: function(word) {
			return indefiniteArticle(word).toLowerCase();
		},

		vehicle: function( i ) {
			return vehicles[i - 1];
		},

		vehicleVar: function( i ) {
			return vehicles[i - 1].charAt(0);
		},

		course: function( i ) {
			return courses[i - 1];
		},

		courseVar: function( i ) {
			return courses[i - 1].charAt(0).toLowerCase();
		},

		exam: function( i ) {
			return exams[i - 1];
		},

		binop: function( i ) {
			return binops[i - 1];
		},

		item: function( i ) {
			return collections[i - 1][0];
		},

		group: function( i ) {
				return collections[i - 1][1];
		},

		groupVerb: function( i ) {
			return collections[i - 1][2];
		},


		store: function( i ) {
			return stores[i].name;
		},

		storeItem: function( i, j ) {
			return stores[i].items[j];
		},

		pizza: function( i ) {
			return pizzas[i];
		},

		exercise: function( i ) {
			return exercises[i - 1];
		},

		timeofday: function( i ) {
			return timesofday[i - 1];
		},

		school: function( i ) {
			return schools[i - 1];
		},

		clothing: function( i ) {
			return clothes[i - 1];
		},

		color: function( i ) {
			return colors[i - 1];
		},

		fruit: function( i ) {
			return fruits[i];
		},

		dier: function (i) {
			return dieren[i];
		},

		kleur: function( i ) {
			return kleuren[i];
		},

		les: function( i ) {
			return lessen[i];
		},

		deskItem: function( i ) {
			return deskItems[i];
		},

		distance: function( i ) {
			return distances[i - 1];
		},

		rode: function( i ) {
			return distanceActivities[i - 1].past;
		},

		ride: function( i ) {
			return distanceActivities[i - 1].present;
		},

		toevoeging: function (i) {
			return distanceActivities[i - 1].voorzetsel;
		},

		bike: function( i ) {
			return distanceActivities[i - 1].noun;
		},

		werkwoord: function (i) {
			return distanceActivities[i - 1].werkwoorden;
		},

		voltooiddlw: function (i) {
			return distanceActivities[i - 1].voltooiddeelwoord;
		},

		biked: function( i ) {
			return distanceActivities[i - 1].done;
		},

		biking: function( i ) {
			return distanceActivities[i - 1].continuous;
		},

		farmer: function( i ) {
			return farmers[i - 1].farmer;
		},

		crop: function( i ) {
			return farmers[i - 1].crops[0];
		},

		fields: function (i) {
			return farmers[i - 1].fieldss;
		},

		field: function( i ) {
			return farmers[i - 1].field;
		},

		side: function( i ) {
			return sides[i - 1];
		},

		shirtStyle: function( i ) {
			return shirtStyles[i - 1];
		},

		animal: function( i ) {
			return animals[i - 1][0];
		},

		animalAvgLifespan: function( i ) {
			return animals[i - 1][1];
		},

		animalStddevLifespan: function( i ) {
			return animals[i - 1][2];
		}
	});
};