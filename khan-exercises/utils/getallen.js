$.extend(KhanUtil, {


    // A function that, given the number, will return the written 
    // equivalent in Dutch

    schrijven: function(num) {
    	var getallen = ["een", "twee", "drie", "vier", "vijf", "zes", "zeven",
    	"acht", "negen", "tien", "elf", "twaalf", "dertien", "veertien", 
    	"vijftien", "zestien", "zeventien",	"achttien", "negentien", "twintig",
    	"eenentwintig", "tweeëntwintig", "drieëntwintig", "vierentwintig",
    	"vijfentwintig", "zesentwintig", "zevenentwintig", "achtentwintig", 
    	"negenentwintig", "dertig", "eenendertig", "tweeëndertig", 
    	"drieëndertig", "vierendertig", "vijfendertig", "zesendertig",
    	"zevenendertig", "achtendertig", "negenendertig", "veertig", 
    	"eenenveertig", "tweeënveertig", "drieënveertig", "vierenveertig",
    	"vijfenveertig", "zesenveertig", "zevenenveertig", "achtenveertig",
    	"negenenveertig", "vijftig", "eenenvijftig", "tweeënvijftig", 
    	"drieënvijftig", "vierenvijftig", "vijfenvijftig", "zesenvijftig", 
    	"zevenenvijftig", "achtenvijftig", "negenenvijftig", "zestig", 
    	"eenenzestig", "tweeënzestig", "drieënzestig", "vierenzestig", 
    	"vijfenzestig", "zesenzestig", "zevenenzestig", "achtenzestig",
    	"negenenzestig", "zeventig", "eenenzeventig", "tweeënzeventig", 
    	"drieënzeventig", "vierenzeventig", "achtenzeventig", 
    	"negenenzeventig", "tachtig", "eenentachtig", "tweeëntachtig",
    	"drieëntachtig", "vierentachtig", "vijfentachtig", "zesentachtig",
    	"zevenentachtig", "achtentachtig", "negenentachtig", "negentig",
    	"eenennegentig", "tweeënnegentig", "drieënnegentig", "vierenegentig",
    	"vijfennegentig", "zesennegentig", "zevenennegentig", "achtennegentig",
    	"negenennegentig", "honderd"];
    	return getallen[ num -1 ];
    },

    isGreater: function(Number1,Number2) {
        if (Number1 > Number2) {
           return Number1/*"Vóór";/*Number1*/
        } else {
            return Number2/*"Na"/*Number2*/
        }
    },

    isSmaller: function(Number1,Number2) {
        if (Number1 < Number2) {
            return Number1;
        } else {return Number2}
    },

    rangtelwoorden: function(rang) {
        var rangen = ["eerste", "tweede", "derde", "vierde", "vijfde", "zesde",
        "zevende", "achtste", "negende", "tiende"];
        return rangen[ rang - 1];
    },

    maanden: function(nummer) {
        var lijstvanmaanden = ["januari", "februari", "maart", "april", "mei",
        "juni", "juli", "augustus", "september", "oktober", "november", "december"];
        return lijstvanmaanden[ nummer - 1];
    }
})