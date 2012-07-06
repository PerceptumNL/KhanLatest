/*
 * This humble dropdown has strayed away from its bootstrap origins
 * enough to warrant its own documentation.

    Sample usage:
    <div class="dropdown">
        <span class="dropdown-toggle">Interact with me to toggle!</span>
        <ul class="dropdown-menu">
            <li><a href="foo">Foo</a></li>
            <li><a href="moo">Moo</a></li>
        </ul>
    </div>

    To initialize
    -- with click to toggle:
        $(".dropdown-toggle").dropdown();
    -- with hover to toggle:
        $(".dropdown-toggle").dropdown("hover");

    If you want to listen for open and close events:
        $(".dropdown-toggle").dropdown()
            .bind("open", function() {
                console.log("Hey, I'm open!");
            }).bind("close", function() {
                console.log("Oops, closed.");
            });

    If you want to programmatically open/close/toggle:
        $(".dropdown-toggle").dropdown("open");
 */


/* ============================================================
 * bootstrap-dropdown.js v2.0.1
 * http://twitter.github.com/bootstrap/javascript.html#dropdowns
 * ============================================================
 * Copyright 2012 Twitter, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ============================================================ */


!function( $ ){

  "use strict"

 /* DROPDOWN CLASS DEFINITION
  * ========================= */

  var toggle = '.dropdown-toggle'
    , Dropdown = function ( element, option ) {
        if (option === 'hover') {
            $(element).on('mouseenter', function() {
                $(this).dropdown('open')
            }).parent().on('mouseleave', function() {
                $(this).find('.dropdown-toggle').dropdown('close')
            }).find('.caret').on('click', function() {
                $(this).parent().dropdown('toggle')
                return false
            })
        } else {
            $(element).on('click.dropdown.data-api', this.toggle)
        }
      }

  Dropdown.prototype = {

    constructor: Dropdown

  , toggle: function ( e ) {
      // TODO(marcia): Investigate whether it would abide by convention more
      // to have `this` refer to Dropdown instead of an html element.
      // Fun fact: bootstrap-modal doesn't follow the below approach.
      var $this = $(this)
        , selector = $this.attr('data-target')
        , $parent
        , isActive

      if (!selector) {
        selector = $this.attr('href')
        selector = selector && selector.replace(/.*(?=#[^\s]*$)/, '') //strip for ie7
      }

      $parent = $(selector)
      $parent.length || ($parent = $this.parent())

      isActive = $parent.hasClass('open')

      if (isActive) {
        Dropdown.prototype.close.call(this)
      } else {
        Dropdown.prototype.open.call(this)
      }

      return false
    }
  , open: function () {
      var $this = $(this)

      if ($this.hasClass('caret')) {
          $this = $this.parent()
      }
      $this.trigger('open')
        .parent().addClass('open')
    }
  , close: function () {
      var $this = $(this)

      $this.trigger('close')
        .parent().removeClass('open')
    }
  }

  function clearMenus(ev) {
    if (ev.originalEvent && ev.originalEvent.leaveDropdownOpen) return
    $(toggle).trigger('close')
        .parent().removeClass('open')
  }


  /* DROPDOWN PLUGIN DEFINITION
   * ========================== */

  $.fn.dropdown = function ( option ) {
    return this.each(function () {
      var $this = $(this)
        , data = $this.data('dropdown')
      if (!data) {
          $this.data('dropdown', (data = new Dropdown(this, option)))
      }
      if (typeof option == 'string') {
          var action = data[option]
          if (action) {
              action.call(this)
          }
      }
    })
  }

  $.fn.dropdown.Constructor = Dropdown


  /* APPLY TO STANDARD DROPDOWN ELEMENTS
   * =================================== */

  $(function () {
    $('html').on('click.dropdown.data-api', clearMenus)
  })

}( window.jQuery );
