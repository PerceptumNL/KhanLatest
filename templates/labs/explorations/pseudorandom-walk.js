(function() {
  var pseudorandom = function(seed) {
    var oldSeed = new BigNumber(seed);
    var oldSeedString = seed;
    var newSeed = oldSeed.multiply(oldSeed);
    var newSeedString = newSeed.toString();
    while (newSeedString.length < oldSeedString.length * 2) {
      newSeedString += '1';
    }
    var begin = Math.floor((newSeedString.length - oldSeedString.length) / 2);
    var end = begin + oldSeedString.length;
    return newSeedString.slice(begin, end);
  };

  $(function() {
    var canvas = Raphael("canvas", 620, 620);
    var clearButton = $('#clear');
    var fromX = 310.5;
    var fromX2 = 310.5;
    var fromY = 310.5;
    var fromY2 = 310.5;
    var seedInput = $('#seed');
    var timeout = null;
    var walkButton = $('#walk');
    clearButton.on('click', function() {
      clearTimeout(timeout);
      return canvas.clear();
    });
    var walk = function(seed) {
      var toX, toXDelta, toY, toYDelta;
      for (var i = 1; i <= 10; i++) {
        toXDelta = [-1, 0, 1][Math.floor(Math.random() * 3)];
        toYDelta = [-1, 0, 1][Math.floor(Math.random() * 3)];
        for (var j = 1; j <= 3; j++) {
          toX = fromX + toXDelta;
          if (toX < .5) {
            toX = 619.5;
            fromX = 619.5;
          }
          if (toX > 619.5) {
            toX = .5;
            fromX = .5;
          }
          toY = fromY + toYDelta;
          if (toY < .5) {
            toY = 619.5;
            fromY = 619.5;
          }
          if (toY > 619.5) {
            toY = .5;
            fromY = .5;
          }
          canvas.path("M" + fromX + "," + fromY + "L" + toX + "," + toY).attr({stroke: "red"});
          fromX = toX;
          fromY = toY;
        }
        toXDelta = [-1, 0, 1][seed % 3];
        seed = pseudorandom(seed);
        toYDelta = [-1, 0, 1][seed % 3];
        seed = pseudorandom(seed);
        for (j = 1; j <= 3; j++) {
          toX = fromX2 + toXDelta;
          if (toX < .5) {
            toX = 619.5;
            fromX2 = 619.5;
          }
          if (toX > 619.5) {
            toX = .5;
            fromX2 = .5;
          }
          toY = fromY2 + toYDelta;
          if (toY < .5) {
            toY = 619.5;
            fromY2 = 619.5;
          }
          if (toY > 619.5) {
            toY = .5;
            fromY2 = .5;
          }
          canvas.path("M" + fromX2 + "," + fromY2 + "L" + toX + "," + toY).attr({stroke: "blue"});
          fromX2 = toX;
          fromY2 = toY;
        }
      }
      return timeout = setTimeout(function() {
        return walk(seed);
      }, 10);
    };
    return walkButton.on('click', function() {
      clearTimeout(timeout);
      fromX = 310.5;
      fromX2 = 310.5;
      fromY = 310.5;
      fromY2 = 310.5;
      return walk(seedInput.val());
    });
  });

}).call(this);
