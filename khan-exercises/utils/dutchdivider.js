/*Taken from graphie-helpers-arithmetic.js, edited to make a Dutch version (staartdelingen)*/


function drawDigits(digits, startX, startY, color) {
    var graph = KhanUtil.currentGraph;
    var set = [];
    $.each(digits, function(index, digit) {
        var str = "\\LARGE{" + digit + "}";
        set.push(graph.label([startX + index, startY], str, { color: color }));
    });
    return set;
}

//same as drawDigits, except changes place of quotient to shift to the right instead of the top
function drawDigits2(digits, startX, startY, color) {
    var graph = KhanUtil.currentGraph;
    var set = [];
    $.each(digits, function(index, digit) {
        var str = "\\LARGE{" + digit + "}";
        set.push(graph.label([startX+6, startY], str, { color: color }));
    });
    return set;
}

function Divider(divisor, dividend, deciDivisor, deciDividend) {
    var graph = KhanUtil.currentGraph;
    var digitsDivisor = KhanUtil.integerToDigits(divisor);
    var digitsDividend = KhanUtil.integerToDigits(dividend);
    deciDivisor = deciDivisor || 0;
    deciDividend = deciDividend || 0;
    var deciDiff = deciDivisor - deciDividend;
    var highlights = [];
    var index = 0;
    var remainder = 0;
    var fOnlyZeros = true;
    var fShowFirstHalf = true;
    var leadingZeros = [];
    var value = 0;
    var decimals = [];

    this.show = function() {
        var paddedDivisor = digitsDivisor;

        if (deciDivisor !== 0) {
            paddedDivisor = (KhanUtil.padDigitsToNum(digitsDivisor.reverse(), deciDivisor + 1)).reverse();
        }
		//Location of entire graphie stuff
        graph.init({
            range: [[-1 - paddedDivisor.length, 17], [(digitsDividend.length + (deciDiff > 0 ? deciDiff : 0)) * -2 - 1, 2]],
            scale: [20, 40]
        });
        graph.style({
            fill: "#000"
        }, function() {
            if (deciDivisor !== 0) {
                decimals = decimals.concat(graph.ellipse([-1 - deciDivisor, -0.2], [0.08, 0.04]));
            }
            if (deciDividend !== 0) {
                decimals = decimals.concat(graph.ellipse([digitsDividend.length - deciDividend - 0.5, -0.2], [0.08, 0.04]));
            }
        });

        drawDigits(paddedDivisor, -0.5 - paddedDivisor.length, 0);
        drawDigits(digitsDividend, 0, 0);
       // graph.path([[-0.75,0.5], [digitsDividend.length, 0.5]]); //drawing the division (list of paths) from -1 (just before quotient) to the length of quotient
		graph.path([[-1.25, -0.4], [-0.5, 0.5]]); //drawing the left bar
		graph.path([[digitsDividend.length-0.25, 0.5],[digitsDividend.length+0.5, -0.4]]); //drawing the right bar


    };

    this.showHint = function() {
        this.removeHighlights();
        if (index === digitsDividend.length) {
            while (leadingZeros.length) {
                leadingZeros.pop().remove();
            }
            return;
        }
		//This is true in the beginning, then sets to false
        if (fShowFirstHalf) {
            value = digitsDividend[index]; //get the number from the dividend-array?
            var quotient = value / divisor; //quotient is that number divided by the divisor
            var total = value + remainder; //total is value + remainder, remainder is 0 at first, later on 10* remainder of prev no.
            highlights = highlights.concat(drawDigits([value], index, 0, KhanUtil.BLUE));
            if (index !== 0) { //if not at the first digit
                graph.style({
                    arrows: "->"
                }, function() {
                    highlights.push(graph.path([[index, 0 - 0.5], [index, -2 * index + 0.5]]));
                });
            }

            drawDigits([value], index, -2 * index);
            var totalDigits = KhanUtil.integerToDigits(total); //turn var total into array of digits
            highlights = highlights.concat(drawDigits(totalDigits, index - totalDigits.length + 1, -2 * index, KhanUtil.BLUE));

            graph.label([digitsDividend.length + 0.5, -2 * (index+1)], //question hints go a little higher
                "\\text{Hoe vaak past }"
                + divisor
                + "\\text{ in }"
                + "\\color{#6495ED}{" + total + "}"
                + "\\text{?}", "right");

            fShowFirstHalf = false;
        } else { //once fShowFirstHalf is set to false, this runs, then sets the var back to true
            value += remainder; //add remainder to var value
            var quotient = Math.floor(value / divisor); //get the floor of value/divisor 
            var diff = value - (quotient * divisor); //get leftover no
            remainder = diff * 10; //assign 10 * leftover to remainder (to switch to the next set of numbers later)
            var quotientLabel = drawDigits2([quotient], index, 0); 
            if (quotient === 0 && fOnlyZeros && digitsDividend.length - deciDividend + deciDivisor > index + 1) {
                leadingZeros = leadingZeros.concat(quotientLabel);
            } else {
                fOnlyZeros = false;
            }
            highlights = highlights.concat(drawDigits2([quotient], index, 0, KhanUtil.GREEN));

            var product = KhanUtil.integerToDigits(divisor * quotient); //put divisor * quotient in array of digits
            drawDigits(product, index - product.length + 1, -2 * index - 1);
            highlights = highlights.concat(drawDigits(product, index - product.length + 1, -2 * index - 1, KhanUtil.ORANGE));

            var diffDigits = KhanUtil.integerToDigits(diff); //put leftover in array of digits
            drawDigits(diffDigits, index - diffDigits.length + 1, -2 * index - 2);

            graph.label([index - product.length, -2 * index - 1] , "-\\vphantom{0}");
            graph.path([[index - product.length - 0.25, -2 * index - 1.5], [index + 0.5, -2 * index - 1.5]]);

            graph.label([digitsDividend.length + 0.5, -2 * (index+1.5)], //hints w formula go a little under the others
                "\\color{#6495ED}{" + value + "}"
                + "\\div"
                + divisor + "="
                + "\\color{#28AE7B}{" + quotient + "}", "right");
            index++;
            fShowFirstHalf = true;

			
        }
    }

    this.addDecimalRemainder = function() {
        dividend = dividend * 10;
        digitsDividend = KhanUtil.integerToDigits(dividend);
        deciDividend = 1;
        deciDiff = deciDivisor - deciDividend;

        this.addDecimal();
        this.show();
        graph.label([digitsDividend.length, 1],
                "\\text{Schrijf een komma en een nul en ga door met delen.}", "right");
    };

    this.getNumHints = function() {
        return Divider.numHintsFor(divisor, dividend, deciDivisor, deciDividend);
    };

    this.removeHighlights = function() {
        while (highlights.length) {
            highlights.pop().remove();
        }
    };

    this.addDecimal = function() {
        graph.style({
                fill: "#000"
            }, function() {
                graph.ellipse([digitsDividend.length + deciDiff - 0.5, -0.2], [0.08, 0.04]);
                graph.ellipse([digitsDividend.length + deciDiff - 0.5, 0.8], [0.08, 0.04]);
            });
    }

    this.shiftDecimals = function() {
        while (decimals.length) {
            decimals.pop().remove();
        }

        if (deciDivisor !== 0) {
            graph.label([digitsDividend.length + 1 + (deciDiff > 0 ? deciDiff : 0), 1],
                "\\text{Verplaats het kommagetal " + deciDivisor + " naar rechts.}", "right");
            graph.style({
                fill: "#000"
            }, function() {
                graph.ellipse([-1, -0.2], [0.08, 0.04]);
            });
        } else {
            graph.label([digitsDividend.length + 0.5, 1.2],
                "\\text{Breng het decimale getal}", "right");
            graph.label([digitsDividend.length + 0.5, 0.8],
                "\\text{in het antwoord (de quotiënt).}", "right");
        }

        this.addDecimal();

        if (deciDiff > 0) {
            var orig = digitsDividend;
            digitsDividend = KhanUtil.padDigitsToNum(digitsDividend, digitsDividend.length + deciDiff);
            drawDigits(digitsDividend, 0, 0);
            highlights = highlights.concat(drawDigits(digitsDividend, 0, 0, KhanUtil.PINK));
            highlights = highlights.concat(drawDigits(orig, 0, 0));
        }
    };
}

Divider.numHintsFor = function(divisor, dividend, deciDivisor, deciDividend) {
    var digitsDividend = KhanUtil.integerToDigits(dividend);
    return 1 + (digitsDividend.length + Math.max(deciDivisor - deciDividend, 0)) * 2;
};

KhanUtil.Divider = Divider;
