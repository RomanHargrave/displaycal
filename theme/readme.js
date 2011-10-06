function $maketoggle(trigger_selector, toggle_selector, return_value) {
	if (return_value == null) return_value = true;
	$(trigger_selector).css('cursor', 'pointer').hover(function () {
		$(this).addClass('hover');
	},
	function () {
		$(this).removeClass('hover');
	}).click(function () {
		var $this = $(this);
		if ($this.hasClass('collapsed')) $this.removeClass('collapsed').addClass('expanded');
		else $this.removeClass('expanded').addClass('collapsed');
		$this.next(toggle_selector).slideToggle();
		return return_value;
	}).addClass('collapsed clickable').next(toggle_selector).hide();
};

function $makeslider(container_selector, toggle_selector, class_name, effect) {
	if (!effect) effect = 'slideToggle';
	$(toggle_selector).hide();
	$(container_selector).addClass(class_name);
	$('a[href^="' + toggle_selector + '"]').click(function () {
		$(toggle_selector + ' .close-button').click();
		return false;
	}).addClass('off');
	$('<div class="close-button">Close</div>').click(function () {
		if ($('a[href^="' + toggle_selector + '"]').hasClass('off')) $('a[href^="' + toggle_selector + '"]').removeClass('off').addClass('on');
		else $('a[href^="' + toggle_selector + '"]').removeClass('on').addClass('off');
		$(toggle_selector)[effect]();
		return false;
	}).appendTo(toggle_selector);
};

jQuery(function ($) {
	/* Infobox slider */
	$('<div id="info-link-box"><a href="#info">i</a></div>').prependTo('#infobox');
	$makeslider('#infobox', '#info', 'fixed-top');
	
	/* Donation box slider */
	$makeslider('#donation-box', '#donate', 'fixed-center', 'fadeToggle');
	
	/* TOC toggles */
	$maketoggle('#toc li:has(ul) > a', 'ul', false);
	
	/* Download toggle */
	$maketoggle('#download h3', 'div');
	
	/* Linux downloads combo */
	$('#download div > ul').before('<div><a class="button" href="https://build.opensuse.org/package/show?package=dispcalGUI&project=home%3Afhoech">Select a package... ▼</a></div>').wrap('<div style="position: relative" />')/*.css({'position': 'absolute', 'z-index': 999})*/.hide();
	$('#download div > div > a.button').mousedown(function () {
		$('#download div > div > ul').slideToggle();
		return false;
	}).click(function () {
		return false;
	});
	
	/* Quickstart sub toggle */
	$maketoggle('#quickstart h3', 'div.optional');
	
	/* Quickstart sub sub toggle */
	$maketoggle('#quickstart h4, #quickstart h5', 'ol, p');
	
	/* Requirements toggle */
	$maketoggle('#requirements-source h3', 'div');
	
	/* Install toggle */
	$maketoggle('#install h3', 'div');
	
	/* Hide issues list */
	$('#issues > ul').hide();
	
	/* Issues toggle */
	$maketoggle('#issues dt', '#issues dd');
	
	/* Issues toggle on link click */
	$('a[href^="#issue-"]').click(function() {
		if (!$($(this).attr('href')).hasClass('expanded')) $($(this).attr('href')).click();
		return true;
	});
	
	/* Changelog toggle */
	$maketoggle('#changelog dt', 'dd');
	$('#changelog dt').first().click();
	
	/* Mail */
	$('a:not([href])').each(function () {
		var $this = $(this),
			at = ' ‹at› ';
		if ($this.html().indexOf(at) > -1) {
			var email = $this.html().split(at).join('@').split(/\s+/).join('');
			$this.attr('href', 'mailto:' + email).html(email);
		}
	});
	
	/* Indent after br */
	$('#content br').after('<span class="indent"></span>')
});
