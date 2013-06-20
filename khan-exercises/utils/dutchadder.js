function Adder(a, b, digitsA, digitsB) {
    var graph = KhanUtil.currentGraph;
    digitsA = digitsA || KhanUtil.digits(a);
    digitsB = digitsB || KhanUtil.digits(b);
    var highlights = [];
    var carry = 0;
    var pos = { max: Math.max(digitsA.length, digitsB.length, KhanUtil.digits(a + b).length),
        carry: 3,
        first: 2,
        second: 1,
        sum: 0,
        sideX: Math.max(digitsA.length, digitsB.length) + 2,
        sideY: 1.5 };

    var index = 0;
    var numHints = Adder.numHintsFor(a, b);

    this.show = function() {
        graph.init({
            range: [[-1, 11], [pos.sum - 0.5, pos.carry + 0.5]],
            scale: [20, 40]
        });

        drawDigits(digitsA.slice(0).reverse(), pos.max - digitsA.length + 1, pos.first);
        drawDigits(digitsB.slice(0).reverse(), pos.max - digitsB.length + 1, pos.second);

        graph.path([[-0.5, pos.second - 0.5], [pos.max + 0.5, pos.second - 0.5]]);
        graph.label([0, 1] , "\\LARGE{+\\vphantom{0}}");
    };

    this.showHint = function() {
        this.removeHighlights();
        if ((index === numHints - 2) && (numHints - 1 > digitsA.length)) {
            this.showFinalCarry();
            index++;
            return;
        } else if (index === numHints - 1) {
            return;
        }
        var prevCarry = carry;
        var prevCarryStr = "";
        var carryStr = "";
        var addendStr = "";
        var sum;

        var x = pos.max - index;

        if (prevCarry !== 0) {
            highlights.push(graph.label([x, pos.carry], "\\color{#6495ED}{" + prevCarry + "}", "below"));
            prevCarryStr = "\\color{#6495ED}{" + prevCarry + "} + ";
        }

        sum = digitsA[index] + carry;
        highlights = highlights.concat(drawDigits([digitsA[index]], x, pos.first, KhanUtil.BLUE));

        if (index < digitsB.length) {
            highlights = highlights.concat(drawDigits([digitsB[index]], x, pos.second, KhanUtil.BLUE));
            addendStr = " + \\color{#6495ED}{" + digitsB[index] + "}";
            sum += digitsB[index];
        }

        drawDigits([sum % 10], x, pos.sum);
        highlights = highlights.concat(drawDigits([sum % 10], x, pos.sum, KhanUtil.GREEN));

        carry = Math.floor(sum / 10);
        if (carry !== 0) {
            highlights.push(graph.label([x - 1, pos.carry],
                "\\color{#FFA500}{" + carry + "}", "below"));
            carryStr = "\\color{#FFA500}{" + carry + "}";
        }

        this.showSideLabel("\\Large{"
            + prevCarryStr
            + "\\color{#6495ED}{" + digitsA[index] + "}"
            + addendStr
            + " = "
            + carryStr
            + "\\color{#28AE7B}{" + sum % 10 + "}"
            + "}");

        index++;
    };

    this.showFinalCarry = function() {
        highlights.push(graph.label([pos.max - index, pos.carry],
            "\\color{#6495ED}{" + carry + "}", "below"));
        graph.label([pos.max - index, pos.sum], "\\LARGE{" + carry + "}");
        highlights.push(graph.label([pos.max - index, pos.sum],
            "\\LARGE{\\color{#28AE7B}{" + carry + "}}"));

        this.showSideLabel("\\Large{"
            + "\\color{#6495ED}{" + carry + "}"
            + " = "
            + "\\color{#28AE7B}{" + carry + "}"
            + "}");
    };

    this.getNumHints = function() {
        return numHints;
    };

    this.removeHighlights = function() {
        while (highlights.length) {
            highlights.pop().remove();
        }
    };

    this.showSideLabel = function(str) {
        highlights.push(graph.label([pos.sideX, pos.sideY], str, "right"));
    };

    this.showDecimals = function(deciA, deciB) {
        for (var i = 0; i < 3; i++) {
            graph.style({ fill: "#000" }, function() {
                graph.ellipse([pos.max - Math.max(deciA, deciB) + 0.5, i - 0.2], [0.06, 0.03]);
				graph.arc([pos.max - Math.max(deciA, deciB)+0.4, i-0.18], 0.2, 270, 360);
            });
        }
        this.showSideLabel("\\text{Zet de kommagetallen op de goede plek.}");
    }
}

Adder.numHintsFor = function(a, b) {
    return KhanUtil.digits(a + b).length + 1;
};

function Subtractor(a, b, digitsA, digitsB, decimalPlaces) {
    var graph = KhanUtil.currentGraph;
    digitsA = digitsA || KhanUtil.digits(a);
    digitsB = digitsB || KhanUtil.digits(b);
    var workingDigitsA = digitsA.slice(0);
    var workingDigitsB = digitsB.slice(0);
    var highlights = [];
    var carry = 0;
    var pos = { max: digitsA.length,
        carry: 3,
        first: 2,
        second: 1,
        diff: 0,
        sideX: Math.max(digitsA.length, digitsB.length) + 2,
        sideY: 1.5 };

    var index = 0;
    var numHints = Subtractor.numHintsFor(a, b);
    decimalPlaces = decimalPlaces || 0;

    this.show = function() {
        graph.init({
            range: [[-1, 11], [pos.diff - 0.5, pos.carry + 0.5]],
            scale: [20, 40]
        });
        drawDigits(digitsA.slice(0).reverse(), pos.max - digitsA.length + 1, pos.first);
        drawDigits(digitsB.slice(0).reverse(), pos.max - digitsB.length + 1, pos.second);

        graph.path([[-0.5, pos.second - 0.5], [pos.max + 0.5, pos.second - 0.5]]);
        graph.label([0, 1] , "\\LARGE{-\\vphantom{0}}");

        for (var i = 0; i < digitsA.length; i++) {
            highlights.unshift([]);
        }
    };

    this.borrow = function(idx) {
        var borrowedIdx = idx + 1;
        if (workingDigitsA[idx + 1] < 1) {
            borrowedIdx = this.borrow(idx + 1);
        }
        workingDigitsA[idx + 1] -= 1;
        workingDigitsA[idx] += 10;

        var depth = borrowedIdx - idx - 1;

        highlights[idx].push(graph.label([pos.max - idx, pos.carry + (0.5 * depth)],
                                             "\\color{#6495ED}{" + workingDigitsA[idx] + "}", "below"));
        highlights[idx].push(graph.path([[pos.max - 0.3 - idx, pos.first - 0.4], [pos.max + 0.3 - idx, pos.first + 0.4]]));

        highlights[idx + 1].push(graph.label([pos.max - 1 - idx, pos.carry + (0.5 * depth)],
                                                 "\\color{#FFA500}{" + workingDigitsA[idx + 1] + "}", "below"));
        highlights[idx + 1].push(graph.path([[pos.max - 1.3 - idx, pos.first - 0.4], [pos.max - 0.7 - idx, pos.first + 0.4]]));
        if (depth !== 0) {
            highlights[idx + 1].push(graph.path([[pos.max - 1.3 - idx, pos.carry - 1 + (0.5 * depth)], [pos.max - 0.7 - idx, pos.carry - 0.7 + (0.5 * depth)]]));
        }
        return borrowedIdx;
    };

    this.showHint = function() {
        this.removeHighlights(index);

        if (index !== 0) {
            this.removeHighlights(index - 1);
        }
        if (index === numHints - 1) {
            return;
        }

        var value = workingDigitsA[index];
        var withinB = index < workingDigitsB.length;
        var subtrahend = withinB ? workingDigitsB[index] : 0;
        var subStr = "";

        if (value < subtrahend) {
            this.borrow(index);
        } else if (workingDigitsA[index] === digitsA[index]) {
            highlights[index].push(graph.label([pos.max - index, pos.first],
                "\\LARGE{\\color{#6495ED}{" + workingDigitsA[index] + "}}"));
        } else {
            highlights[index].push(graph.label([pos.max - index, pos.carry],
                "\\color{#6495ED}{" + workingDigitsA[index] + "}", "below"));
        }

        if (withinB) {
            highlights[index].push(graph.label([pos.max - index, pos.second],
                "\\LARGE{\\color{#6495ED}{" + workingDigitsB[index] + "}}"));
            subStr = " - \\color{#6495ED}{" + subtrahend + "}";
        }

        var diff = workingDigitsA[index] - subtrahend;
        if (((a - b) / Math.pow(10, index)) > 1 || index < decimalPlaces) {
            graph.label([pos.max - index, pos.diff], "\\LARGE{" + diff + "}");
        }

        highlights[index].push(graph.label([pos.max - index, pos.diff], "\\LARGE{\\color{#28AE7B}{" + diff + "}}"));
        if (subStr == "") {
            subStr = "- \\color{#6495ED}{ 0 }";
        }

        this.showSideLabel("\\Large{"
            + "\\color{#6495ED}{" + workingDigitsA[index] + "}"
            + subStr
            + " = "
            + "\\color{#28AE7B}{" + diff + "}}");

        index++;
    };

    this.getNumHints = function() {
        return numHints;
    };

    this.removeHighlights = function(i) {
        if (i >= highlights.length) {
            return;
        }

        var col = highlights[i];
        while (col.length) {
            col.pop().remove();
        }
    };

    this.showSideLabel = function(str) {
        highlights[index].push(graph.label([pos.sideX, pos.sideY], str, "right"));
    };

    this.showDecimals = function(deciA, deciB) {
        for (var i = 0; i < 3; i++) {
            graph.style({ fill: "#000" }, function() {
                graph.ellipse([pos.max - Math.max(deciA, deciB) + 0.5, i - 0.2], [0.06, 0.03]);
				graph.arc([pos.max - Math.max(deciA, deciB)+0.4, i-0.18], 0.2, 270, 360);
            });
        }
        this.showSideLabel("\\text{Zet de kommagetallen op de goede plek.}");
    };
}

Subtractor.numHintsFor = function(a, b) {
    return KhanUtil.digits(a).length + 1;
};

// convert Adder -> DecimalAdder and Subtractor -> DecimalSubtractor
(function() {
    var decimate = function(drawer) {
        var news = function(a, aDecimal, b, bDecimal) {
            var newA = a * (bDecimal > aDecimal ? Math.pow(10, bDecimal - aDecimal) : 1);
            var newB = b * (aDecimal > bDecimal ? Math.pow(10, aDecimal - bDecimal) : 1);
            return [newA, newB];
        };

        var decimated = function(a, aDecimal, b, bDecimal) {
            var newAB = news(a, aDecimal, b, bDecimal);
            var newA = newAB[0], newB = newAB[1];

            var aDigits = KhanUtil.digits(newA);
            for (var i = 0; i < (aDecimal - bDecimal) || aDigits.length < aDecimal + 1; i++) {
                aDigits.push(0);
            }

            var bDigits = KhanUtil.digits(newB);
            for (var i = 0; i < (bDecimal - aDecimal) || bDigits.length < bDecimal + 1; i++) {
                bDigits.push(0);
            }
            var drawn = new drawer(newA, newB, aDigits, bDigits, Math.max(aDecimal, bDecimal));

            drawn.showDecimals = (function(old) {
                return function() {
                    old.call(drawn, aDecimal, bDecimal);
                }
            })(drawn.showDecimals);

            return drawn;
        };

        decimated.numHintsFor = function(a, aDecimal, b, bDecimal) {
            var newAB = news(a, aDecimal, b, bDecimal);
            var newA = newAB[0], newB = newAB[1];

            return drawer.numHintsFor(newA, newB);
        };

        return decimated;
    };

    // I hate global variables
    DecimalAdder = decimate(Adder);
    DecimalSubtractor = decimate(Subtractor);
})();




function drawDigits(digits, startX, startY, color) {
    var graph = KhanUtil.currentGraph;
    var set = [];
    $.each(digits, function(index, digit) {
        var str = "\\LARGE{" + digit + "}";
        set.push(graph.label([startX + index, startY], str, { color: color }));
    });
    return set;
}

// for multiplication 0.5, 1
function drawRow(num, y, color, startCount) {
    var graph = KhanUtil.currentGraph;

    graph.style({
        stroke: color
    });

    var set = graph.raphael.set();
    for (var x = 0; x < num; x++) {
        set.push(graph.label([x, y], "\\small{\\color{" + color + "}{" + (startCount + x) + "}}"));
        set.push(graph.circle([x, y], 0.5));
    }

    return set;
}




function Multiplier(a, b, digitsA, digitsB, deciA, deciB) {
    var graph = KhanUtil.currentGraph;
    deciA = deciA || 0;
    deciB = deciB || 0;
    digitsA = digitsA || KhanUtil.digits(a);
    digitsB = digitsB || KhanUtil.digits(b);
    var digitsProduct = KhanUtil.integerToDigits(a * b);
    var highlights = [];
    var carry = 0;
    var numHints = digitsA.length * digitsB.length + 1;
    var indexA = 0;
    var indexB = 0;
    var maxNumDigits = Math.max(deciA + deciB, digitsProduct.length);

    this.show = function() {
        graph.init({
            range: [[-2 - maxNumDigits, 12], [-1 - digitsB.length * digitsA.length, 3]],
            scale: [20, 40]
        });

        drawDigits(digitsA.slice(0).reverse(), 1 - digitsA.length, 2);
        drawDigits(digitsB.slice(0).reverse(), 1 - digitsB.length, 1);

        graph.path([[-1 - digitsProduct.length, 0.5], [1, 0.5]]);
        graph.label([- (Math.max(digitsA.length, digitsB.length)), 1] , "\\LARGE{\\times\\vphantom{0}}");
    };

    this.removeHighlights = function() {
        while (highlights.length) {
            highlights.pop().remove();
        }
    };

    this.showHint = function() {
        this.removeHighlights();

        if (indexB === digitsB.length) {
            this.showFinalAddition();
            return;
        }

        var bigDigit = digitsA[indexA];
        var smallDigit = digitsB[indexB];

        var product = smallDigit * bigDigit + carry;
        var ones = product % 10;
        var currCarry = Math.floor(product / 10);

        highlights = highlights.concat(drawDigits([bigDigit], -indexA, 2, KhanUtil.BLUE));
        highlights = highlights.concat(drawDigits([smallDigit], -indexB, 1, KhanUtil.PINK));
        if (carry) {
            highlights = highlights.concat(graph.label([-indexA, 3], "\\color{#FFA500}{" + carry + "}", "below"));
        }
        graph.label([2, -indexB * digitsA.length - indexA + 2],
            "\\color{#6495ED}{" + bigDigit + "}"
            + "\\times"
            + "\\color{#FF00AF}{" + smallDigit + "}"
            + (carry ? "+\\color{#FFA500}{" + carry + "}" : "")
            + "="
            + "\\color{#28AE7B}{" + product + "}", "right");

        drawDigits([ones], -indexB - indexA, -indexB);
        highlights = highlights.concat(drawDigits([ones], -indexB - indexA, -indexB, KhanUtil.GREEN));

        if (currCarry) {
            highlights = highlights.concat(graph.label([-1 - indexA, 3], "\\color{#28AE7B}{" + currCarry + "}", "below"));
            if (indexA === digitsA.length - 1) {
                drawDigits([currCarry], -indexB - indexA - 1, -indexB);
                highlights = highlights.concat(drawDigits([currCarry], -indexB - indexA - 1, -indexB, KhanUtil.GREEN));
            }
        }
        carry = currCarry;

        if (indexA === digitsA.length - 1) {
            indexB++;
            indexA = 0;
            carry = 0;
        } else {
            indexA++;
        }
    };

    this.showFinalAddition = function() {
        if (digitsB.length > 1) {
            while (digitsProduct.length < deciA + deciB + 1) {
                digitsProduct.unshift(0);
            }
            graph.path([[-1 - digitsProduct.length, 0.5 - digitsB.length], [1, 0.5 - digitsB.length]]);
            graph.label([-1 - digitsProduct.length, 1 - digitsB.length] , "\\LARGE{+\\vphantom{0}}");
            drawDigits(digitsProduct, 1 - digitsProduct.length, -digitsB.length);
        }
    }

    this.getNumHints = function() {
        return numHints;
    };

    this.showDecimals = function() {
        graph.style({
            fill: "#000"
        }, function() {
            if (deciA > 0)
                graph.ellipse([-deciA + 0.5, 1.8], [0.08, 0.04]);
				graph.arc([- deciA + 0.4, 1.8], 0.2, 270, 360); //make dot into comma
            if (deciB > 0)
                graph.ellipse([-deciB + 0.5, 0.8], [0.08, 0.04]);
				graph.arc([-deciB + 0.4, 0.8], 0.2, 270, 360); //make dot into comma
        });
    };

    this.showDecimalsInProduct = function() {
        var x = -maxNumDigits;
        var y = -digitsB.length * digitsA.length;

        graph.label([x, y + 2],
            "\\text{Het bovenste getal heeft " + KhanUtil.plural(deciA, "cijfer") + " achter de komma.}", "right");
        graph.label([x, y + 1],
            "\\text{Het onderste getal heeft " + KhanUtil.plural(deciB, "cijfer") + " achter de komma.}", "right");
        graph.label([x, y],
            "\\text{Het product heeft " + deciA + " + " + deciB + " = " + (deciA + deciB)
             + "  cijfers achter de komma.}", "right");
        graph.style({
            fill: "#000"
        }, function() {
            graph.ellipse([-deciB - deciA + 0.5, -0.2 - digitsB.length], [0.08, 0.04]);
			graph.arc([-deciB - deciA + 0.4, -0.2 - digitsB.length], 0.2, 270, 360);//make dot into comma
        });
    };
}


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
				decimals = decimals.concat(graph.arc([-1 -deciDivisor -0.1, -0.2], 0.2, 270, 360)); //make dot into comma
            }
            if (deciDividend !== 0) {
                decimals = decimals.concat(graph.ellipse([digitsDividend.length - deciDividend - 0.5, -0.2], [0.08, 0.04]));
				decimals = decimals.concat(graph.arc([digitsDividend.length - deciDividend - 0.6, -0.2], 0.2, 270, 360)); //make dot into comma
            }
        });

        drawDigits(paddedDivisor, -0.5 - paddedDivisor.length, 0);
        drawDigits(digitsDividend, 0, 0);
       // graph.path([[-0.75,0.5], [digitsDividend.length, 0.5]]); //drawing the division (list of paths) from -1 (just before quotient) to the length of quotient
		graph.path([[-0.8, -0.4], [-0.5, 0.5]]); //drawing the left bar
		graph.path([[digitsDividend.length-0.1, 0.5],[digitsDividend.length+0.5, -0.4]]); //drawing the right bar


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
                graph.ellipse([digitsDividend.length + deciDiff - 0.5, -0.2], [0.08, 0.04]); //rechtse dot
				graph.arc([digitsDividend.length+deciDiff - 0.6, -0.2], 0.2, 270, 360); // make dot into comma

                graph.ellipse([2*digitsDividend.length +0.5+  deciDiff, -0.2], [0.08, 0.04]); //bovenste dot
				graph.arc([2*digitsDividend.length+0.4 +deciDiff, -0.2],0.2,270,360); //make dot into comma
				//ALMOST WORKS, but sometimes puts the dot in the wrong place for the answer. Not sure yet why.
            });
    }

    this.shiftDecimals = function() {
        while (decimals.length) {
            decimals.pop().remove();
        }

        if (deciDivisor !== 0) {
            graph.label([digitsDividend.length + 1 + (deciDiff > 0 ? deciDiff : 0), 1],
                "\\text{Verplaats de komma " + deciDivisor + " naar rechts.}", "right");
            graph.style({
                fill: "#000"
            }, function() { //verplaats komma
                graph.ellipse([-1, -0.2], [0.08, 0.04]);
				graph.arc([-1.1, -0.2], 0.2, 270, 360); //make dot into comma
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















