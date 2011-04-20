/*
 * jQuery UI Menu @VERSION
 * 
 * Copyright 2011, AUTHORS.txt (http://jqueryui.com/about)
 * Dual licensed under the MIT or GPL Version 2 licenses.
 * http://jquery.org/license
 *
 * http://docs.jquery.com/UI/Menu
 *
 * Depends:
 *	jquery.ui.core.js
 *	jquery.ui.widget.js
 */

/*
 * Prasad:
 *   1. Removed support for submenus
 *   2. Removed support for paging (we don't need it + _hasScroll() seems to be wrong)
 */
(function($) {
	
var idIncrement = 0;

$.widget("ui.menu", {
	defaultElement: "<ul>",
	delay: 150,
	options: {
		position: {
			my: "left top",
			at: "right top"
		}
	},
	_create: function() {
		var self = this;
		this.menuId = this.element.attr( "id" ) || "ui-menu-" + idIncrement++;
		this.element
			.addClass( "ui-menu ui-widget ui-widget-content ui-corner-all" )
			.attr({
				id: this.menuId,
				role: "listbox"
			})
			.bind( "click.menu", function( event ) {
				var item = $( event.target ).closest( ".ui-menu-item:has(a)" );
				if ( self.options.disabled ) {
					return false;
				}
				if ( !item.length ) {
					return;
				}
				// temporary
				event.preventDefault();
				// it's possible to click an item without hovering it (#7085)
				if ( !self.active || ( self.active[ 0 ] !== item[ 0 ] ) ) {
					self.focus( event, item );
				}
				self.select( event );
			})
			.bind( "mouseover.menu", function( event ) {
				if ( self.options.disabled ) {
					return;
				}
				var target = $( event.target ).closest( ".ui-menu-item" );
				if ( target.length ) {
					self.focus( event, target );
				}
			})
			.bind("mouseout.menu", function( event ) {
				if ( self.options.disabled ) {
					return;
				}
				var target = $( event.target ).closest( ".ui-menu-item" );
				if ( target.length ) {
					self.blur( event );
				}
			});
		this.refresh();
		
		this.element.attr( "tabIndex", 0 ).bind( "keydown.menu", function( event ) {
			if ( self.options.disabled ) {
				return;
			}
			switch ( event.keyCode ) {
			case $.ui.keyCode.PAGE_UP:
				self.previousPage( event );
				event.preventDefault();
				event.stopImmediatePropagation();
				break;
			case $.ui.keyCode.PAGE_DOWN:
				self.nextPage( event );
				event.preventDefault();
				event.stopImmediatePropagation();
				break;
			case $.ui.keyCode.UP:
				self.previous( event );
				event.preventDefault();
				event.stopImmediatePropagation();
				break;
			case $.ui.keyCode.DOWN:
				self.next( event );
				event.preventDefault();
				event.stopImmediatePropagation();
				break;
			case $.ui.keyCode.ENTER:
				self.select( event );
				event.preventDefault();
				event.stopImmediatePropagation();
				break;
			}
		});
	},
	
	_destroy: function() {
		this.element
			.removeClass( "ui-menu ui-widget ui-widget-content ui-corner-all" )
			.removeAttr( "tabIndex" )
			.removeAttr( "role" )
			.removeAttr( "aria-activedescendant" );
		
		this.element.children( ".ui-menu-item" )
			.removeClass( "ui-menu-item" )
			.removeAttr( "role" )
			.children( "a" )
			.removeClass( "ui-corner-all ui-state-hover" )
			.removeAttr( "tabIndex" )
			.unbind( ".menu" );
	},
	
	refresh: function() {
		// don't refresh list items that are already adapted
		var items = this.element.children( "li:not(.ui-menu-item):has(a)" )
			.addClass( "ui-menu-item" )
			.attr( "role", "menuitem" );
		
		items.children( "a" )
			.addClass( "ui-corner-all" )
			.attr( "tabIndex", -1 );
	},

	focus: function( event, item ) {
		var self = this;
		
		this.blur();
		this.active = item.first()
			.children( "a" )
				.addClass( "ui-state-focus" )
				.attr( "id", function(index, id) {
					return (self.itemId = id || self.menuId + "-activedescendant");
				})
			.end();
		// need to remove the attribute before adding it for the screenreader to pick up the change
		// see http://groups.google.com/group/jquery-a11y/msg/929e0c1e8c5efc8f
		this.element.removeAttr("aria-activedescendant").attr("aria-activedescendant", self.itemId)
		
		self.timer = setTimeout(function() {
			self._close();
		}, self.delay)
		this._trigger( "focus", event, { item: item } );
	},

	blur: function(event) {
		if (!this.active) {
			return;
		}
		
		clearTimeout(this.timer);
		
		this.active.children( "a" ).removeClass( "ui-state-focus" );
		// remove only generated id
		$( "#" + this.menuId + "-activedescendant" ).removeAttr( "id" );
		this.element.removeAttr( "aria-activedescenant" );
		this._trigger( "blur", event );
		this.active = null;
	},

	closeAll: function() {
		this.element
		 .find("a.ui-state-active").removeClass("ui-state-active");
		this.blur();
	},
	
	_close: function() {
		this.active.parent()
		 .find("a.ui-state-active").removeClass("ui-state-active");
	},

	next: function(event) {
		this._move( "next", ".ui-menu-item", "first", event );
	},

	previous: function(event) {
		this._move( "prev", ".ui-menu-item", "last", event );
	},

	first: function() {
		return this.active && !this.active.prevAll( ".ui-menu-item" ).length;
	},

	last: function() {
		return this.active && !this.active.nextAll( ".ui-menu-item" ).length;
	},

	_move: function(direction, edge, filter, event) {
		if ( !this.active ) {
			this.focus( event, this.element.children(edge)[filter]() );
			return;
		}
		var next = this.active[ direction + "All" ]( ".ui-menu-item" ).eq( 0 );
		if ( next.length ) {
			this.focus( event, next );
		} else {
			this.focus( event, this.element.children(edge)[filter]() );
		}
	},
	
	nextPage: function( event ) {
		this.focus( event, this.element.children( ".ui-menu-item" )
			[ !this.active || this.last() ? "first" : "last" ]() );
	},

	previousPage: function( event ) {
		this.focus( event, this.activeMenu.children( ".ui-menu-item" )
			[ !this.active || this.first() ? ":last" : ":first" ]() );
	},

	_hasScroll: function() {
		return this.element.height() < this.element.attr( "scrollHeight" );
	},

	select: function( event ) {
		// save active reference before closeAll triggers blur
		var ui = {
			item: this.active
		};
		this.closeAll();
		this._trigger( "select", event, ui );
	}
});

$.ui.menu.version = "@VERSION";

}( jQuery ));
