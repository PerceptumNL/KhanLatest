$.extend(KhanUtil, {
    getSmallDigitNumber:function(){
	   switch(this.randRange(2,5)){
			case 1: var n = this.randRange(1,4);
					break;
			case 2: var n1 = this.randRange(1,5);
					var n2 = this.randRange(0,4);
					var tS = String(n1)+String(n2);
					var n = parseInt(tS);
					break;
			case 3: var n1 = this.randRange(1,5);
					var n2 = this.randRange(0,4);
					var n3 = this.randRange(0,4);
					var tS = String(n1)+String(n2)+String(n3);
					var n = parseInt(tS);
					break;
			case 4: var n1 = this.randRange(1,5);
					var n2 = this.randRange(0,4);
					var n3 = this.randRange(0,4);
					var n4 = this.randRange(0,4);
					var tS = String(n1)+String(n2)+String(n3)+String(n4);
					var n = parseInt(tS);
					break;
			case 5: var n1 = this.randRange(1,5);
					var n2 = this.randRange(0,4);
					var n3 = this.randRange(0,4);
					var n4 = this.randRange(0,4);
					var n5 = this.randRange(0,4);
					var tS = String(n1)+String(n2)+String(n3)+String(n4)+String(n5);
					var n = parseInt(tS);
					break;
			default: var n=44;
		}
		return n;
	}
	
});




function liesbethAdder(a, b, c, digitsA, digitsB, digitsC) {
    var graph = KhanUtil.currentGraph;
    digitsA = digitsA || KhanUtil.digits(a);
    digitsB = digitsB || KhanUtil.digits(b);
	digitsC = digitsC || KhanUtil.digits(c);
    var highlights = [];
    var carry = 0;
	
	//=========================================================
	/*
	var pos = { max: Math.max(digitsA.length, digitsB.length, KhanUtil.digits(a + b).length),
        carry: 3,
        first: 2,
        second: 1,
        sum: 0,
        sideX: Math.max(digitsA.length, digitsB.length) + 2,
        sideY: 1.5 };
	*/
    var pos = { max: Math.max(digitsA.length, digitsB.length, KhanUtil.digits(a + b + c).length),
 		carry: 4,
        first: 3,
        second: 2,
		third: 1,		
        sum: 0,
        sideX: Math.max(digitsA.length, digitsB.length,digitsC.length) + 2,
        sideY: 1.5 };
	//======================================================

    var index = 0;
    var numHints = liesbethAdder.numHintsFor(a, b, c);

    this.show = function() {
	   //====================================================
	   /*
	   graph.init({
            range: [[-1, 11], [pos.sum - 0.5, pos.carry + 0.5]],
            scale: [20, 40]
        });
		*/
        graph.init({
            range: [[-1, 11], [pos.sum - 0.5, pos.carry + 0.5]],
            scale: [20, 40]
        });
        //=====================================================
        drawDigits(digitsA.slice(0).reverse(), pos.max - digitsA.length + 1, pos.first);
        drawDigits(digitsB.slice(0).reverse(), pos.max - digitsB.length + 1, pos.second);
		drawDigits(digitsC.slice(0).reverse(), pos.max - digitsC.length + 1, pos.third);

        graph.path([[-0.5, pos.third - 0.5], [pos.max + 0.5, pos.third - 0.5]]);
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

        sum = digitsA[index] + digitsB[index] + carry;
        
		//=================================================
		/*
		highlights = highlights.concat(drawDigits([digitsA[index]], x, pos.first, KhanUtil.BLUE));

        if (index < digitsB.length) {
            highlights = highlights.concat(drawDigits([digitsB[index]], x, pos.second, KhanUtil.BLUE));
            addendStr = " + \\color{#6495ED}{" + digitsB[index] + "}";
            sum += digitsB[index];
        }
        */
		highlights = highlights.concat(drawDigits([digitsA[index]], x, pos.first, KhanUtil.BLUE));
        highlights = highlights.concat(drawDigits([digitsB[index]], x, pos.second, KhanUtil.BLUE));
        if (index < digitsC.length) {
            highlights = highlights.concat(drawDigits([digitsC[index]], x, pos.third, KhanUtil.BLUE));
            addendStr = " + \\color{#6495ED}{" + digitsC[index] + "}";
            sum += digitsC[index];
        }
		//=================================================
		
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
			 + " + "
			+ "\\color{#6495ED}{" + digitsB[index] + "}"
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
                graph.ellipse([pos.max - Math.max(deciA, deciB) + 0.5, i - 0.2], [0.08, 0.04]);
            });
        }
        this.showSideLabel("\\text{Make sure the decimals are lined up.}");
    }
}

liesbethAdder.numHintsFor = function(a, b , c) {
    return KhanUtil.digits(a + b + c).length + 1;
};





