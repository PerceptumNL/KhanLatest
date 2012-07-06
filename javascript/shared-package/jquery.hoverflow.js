/*
* hoverFlow - A Solution to Animation Queue Buildup in jQuery
* Version 1.00
*
* Copyright (c) 2009 Ralf Stoltze, http://www.2meter3.de/code/hoverFlow/
* Dual-licensed under the MIT and GPL licenses.
* http://www.opensource.org/licenses/mit-license.php
* http://www.gnu.org/licenses/gpl.html
*/

/*
 * Modified by Tom Yedwab:
 * - Added directional sensitivity to hoverIntent
 */

(function($) {
    $.fn.hoverFlow = function(type, prop, speed, easing, callback) {
        // only allow hover events
        if ($.inArray(type, ['mouseover', 'mouseenter', 'mouseout', 'mouseleave']) == -1) {
            return this;
        }
    
        // build animation options object from arguments
        // based on internal speed function from jQuery core
        var opt = typeof speed === 'object' ? speed : {
            complete: callback || !callback && easing || $.isFunction(speed) && speed,
            duration: speed,
            easing: callback && easing || easing && !$.isFunction(easing) && easing
        };
        
        // run immediately
        opt.queue = false;
            
        // wrap original callback and add dequeue
        var origCallback = opt.complete;
        opt.complete = function() {
            // execute next function in queue
            $(this).dequeue();
            // execute original callback
            if ($.isFunction(origCallback)) {
                origCallback.call(this);
            }
        };
        
        // keep the chain intact
        return this.each(function() {
            var $this = $(this);
        
            // set flag when mouse is over element
            if (type == 'mouseover' || type == 'mouseenter') {
                $this.data('jQuery.hoverFlow', true);
            } else {
                $this.removeData('jQuery.hoverFlow');
            }
            
            // enqueue function
            $this.queue(function() {                
                // check mouse position at runtime
                var condition = (type == 'mouseover' || type == 'mouseenter') ?
                    // read: true if mouse is over element
                    $this.data('jQuery.hoverFlow') !== undefined :
                    // read: true if mouse is _not_ over element
                    $this.data('jQuery.hoverFlow') === undefined;
                    
                // only execute animation if condition is met, which is:
                // - only run mouseover animation if mouse _is_ currently over the element
                // - only run mouseout animation if the mouse is currently _not_ over the element
                if(condition) {
                    $this.animate(prop, opt);
                // else, clear queue, since there's nothing more to do
                } else {
                    $this.queue([]);
                }
            });

        });
    };
})(jQuery);


/**
* hoverIntent is similar to jQuery's built-in "hover" function except that
* instead of firing the onMouseOver event immediately, hoverIntent checks
* to see if the user's mouse has slowed down (beneath the sensitivity
* threshold) before firing the onMouseOver event.
* 
* hoverIntent r6 // 2011.02.26 // jQuery 1.5.1+
* <http://cherne.net/brian/resources/jquery.hoverIntent.html>
* 
* hoverIntent is currently available for use in all personal or commercial 
* projects under both MIT and GPL licenses. This means that you can choose 
* the license that best suits your project, and use it accordingly.
* 
* // basic usage (just like .hover) receives onMouseOver and onMouseOut functions
* $("ul li").hoverIntent( showNav , hideNav );
* 
* // advanced usage receives configuration object only
* $("ul li").hoverIntent({
*    sensitivity: 7, // number = sensitivity threshold (must be 1 or higher)
*    interval: 100,   // number = milliseconds of polling interval
*   directionalSensitivityX: 0, // number = threshold of horizontal movement that extends the onMouseOut delay (0 = disabled, positive = right, negative = left)
*   directionalSensitivityY: 0, // number = threshold of vertical movement that extends the onMouseOut delay (0 = disabled, positive = down, negative = up)
*    over: showNav,  // function = onMouseOver callback (required)
*    timeout: 0,   // number = milliseconds delay before onMouseOut function call
*    out: hideNav    // function = onMouseOut callback (required)
* });
* 
* @param  f  onMouseOver function || An object with configuration options
* @param  g  onMouseOut function  || Nothing (use configuration options object)
* @author    Brian Cherne brian(at)cherne(dot)net
*/
(function($) {
    $.fn.hoverIntent = function(f,g) {
        // default configuration options
        var cfg = {
            sensitivity: 7,
            directionalSensitivityStop: 0,
            directionalSensitivityX: 0,
            directionalSensitivityY: 0,
            interval: 100,
            timeout: 0
        };
        // override configuration options with user supplied object
        cfg = $.extend(cfg, g ? { over: f, out: g } : f );

        // instantiate variables
        // cX, cY = current X and Y position of mouse, updated by mousemove event
        // pX, pY = previous X and Y position of mouse, set by mouseover and polling interval
        // dX, dY = average X and Y movement velocity, set by mouseover and polling interval
        var cX = 0, cY = 0, pX, pY, dX = 0, dY = 0;

        // A private function for getting mouse position
        var track = function(ev) {
            var curDeltaX = (ev.pageX-cX);
            var curDeltaY = (ev.pageY-cY);
            if (((dX > 0 && curDeltaX > 0) || (dX < 0 && curDeltaX < 0)) &&
                ((dX > 0 && curDeltaX > 0) || (dX < 0 && curDeltaX < 0))) {
                // If the mouse velocity direction hasn't changed, dampen values over several moves
                dX = dX * 0.75 + curDeltaX*0.25;
                dY = dY * 0.75 + curDeltaY*0.25;
            } else {
                // If the mouse velocity has changed, reset delta values
                dX = curDeltaX;
                dY = curDeltaY;
            }
            cX = ev.pageX;
            cY = ev.pageY;
        };

        // A private function for comparing current and previous mouse position
        var compare = function(ev,ob) {
            ob.hoverIntent_t = clearTimeout(ob.hoverIntent_t);
            // compare mouse positions to see if they've crossed the threshold
            if ( ( Math.abs(pX-cX) + Math.abs(pY-cY) ) < cfg.sensitivity) {
                // set hoverIntent state to true (so mouseOut can be called)
                ob.hoverIntent_s = 1;
                return cfg.over.apply(ob,[ev]);
            } else {
                // set previous coordinates for next time
                pX = cX; pY = cY;
                // use self-calling timeout, guarantees intervals are spaced out properly (avoids JavaScript timer bugs)
                ob.hoverIntent_t = setTimeout( function(){compare(ev, ob);} , cfg.interval );
            }
        };

        // A private function for delaying the mouseOut function
        // If directionalSensitivityX (dsX) is positive, horizontal mouse movements over +dSX cancel close. If dSX is negative, horizontal mouse movements less than -dSX cancel close.
        // directionalSensitivityY works the same way.
        var delay = function(ev,ob) {
            ob.hoverIntent_t = clearTimeout(ob.hoverIntent_t);

            if ((cfg.directionalSensitivityX > 0 && dX > cfg.directionalSensitivityX) ||
                 (cfg.directionalSensitivityX < 0 && dX < -cfg.directionalSensitivityX) ||
                 (cfg.directionalSensitivityY > 0 && dY > cfg.directionalSensitivityY) ||
                 (cfg.directionalSensitivityY < 0 && dY < -cfg.directionalSensitivityY)) {
                // set previous coordinates for next time
                pX = cX; pY = cY;
                // Decay deltas if there are no mouseMove events
                dX *= 0.25;
                dY *= 0.25;
                // directional mouse movement causing us to extend the timeout interval
                ob.hoverIntent_t = setTimeout( function(){delay(ev,ob);} , cfg.timeout );
            } else {
                ob.hoverIntent_s = 0;
                // unbind expensive mousemove event
                $(ob).unbind("mousemove",track);
                ob.mouseMoveBound = false;
                return cfg.out.apply(ob,[ev]);
            }
        };

        // A private function for handling mouse 'hovering'
        var handleHover = function(e) {
            // copy objects to be passed into t (required for event object to be passed in IE)
            var ev = jQuery.extend({},e);
            var ob = this;

            // cancel hoverIntent timer if it exists
            if (ob.hoverIntent_t) { ob.hoverIntent_t = clearTimeout(ob.hoverIntent_t); }

            // if e.type == "mouseenter"
            if (e.type == "mouseenter") {
                if (ob.hoverIntent_s != 1) {
                    if (!ob.mouseMoveBound) {
                        // update "current" X and Y position based on mousemove
                        $(ob).bind("mousemove",track);
                        ob.mouseMoveBound = true;
                    }

                    // set "previous" X and Y position based on initial entry point
                    pX = ev.pageX; pY = ev.pageY;
                    // start polling interval (self-calling timeout) to compare mouse coordinates over time
                    ob.hoverIntent_t = setTimeout( function(){compare(ev,ob);} , cfg.interval );
                }

            // else e.type == "mouseleave"
            } else {
                // if hoverIntent state is true, then call the mouseOut function after the specified delay
                if (ob.hoverIntent_s == 1) {
                    // set "previous" X and Y position based on exit point
                    pX = ev.pageX; pY = ev.pageY;
                    // delay mouseout until time passes (and directional threshold hasn't been met)
                    ob.hoverIntent_t = setTimeout( function(){delay(ev,ob);} , cfg.timeout );
                }
            }
        };

        // bind the function to the two event listeners
        return this.bind('mouseenter',handleHover).bind('mouseleave',handleHover);
    };
})(jQuery);
