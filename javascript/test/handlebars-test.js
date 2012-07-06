/**
 * Node.js script that is called by handlebars.py during unit tests.
 * Compiles & executes a Handlebars template, writing result to STDOUT.
 */

var fs = require("fs");
_ = require("../../tools/node_modules/underscore");
Handlebars = require("../../tools/node_modules/handlebars");

var partials = {};
Templates = {
    get: function(name) {
        name = name.replace(".", "_");
        return partials[name] || null;
    }
}; // For a registerPartial call

require("../shared-package/handlebars-extras.js");
require("../profile-package/handlebars-helpers.js");

var sourceFile = process.argv[2];

var source = fs.readFileSync(sourceFile, "utf8");

function importPartial(partial) {
    if (!partials[partial]) {
        var sp = partial.split("_");
        var package = sp[0];
        var name = sp[1];
        var filename = "javascript/" + package + "-package/" + name + ".handlebars";

        var partialSource = fs.readFileSync(filename, "utf8");
        var fn = Handlebars.compile(partialSource);
        Handlebars.registerPartial(partial, fn);
        partials[partial] = fn;

        importPartials(partialSource);
    }
}

function importPartials(source) {
    var partialRegExp = /{{>[\s]*([\w-_]+)[\s]*}}/g
    var partial;
    do {
        partial = partialRegExp.exec(source);
        if (partial) {
            importPartial(partial[1]);
        }
    } while (partial);
}

importPartials(source);
importPartial("shared_skill-bar"); // Used by skill-bar helper

var template = Handlebars.compile(source);

var dataText = fs.readFileSync(process.argv[3], "utf8");
var dataParsed = JSON.parse(dataText);

try {
    var result = template(dataParsed);
    console.log(result);
} catch (e) {
    console.log("Exception thrown: ", e, e.stack);
}
