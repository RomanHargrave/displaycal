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

function $splash_anim(i, splash_frames) {
	if (i == splash_frames.length) {
		$('#splash').fadeOut(566, function () {
			$('#splash_version_string, .splash_anim').hide();
			$('#splash').addClass('folded');
			$('#splash').css({'background-image': 'url(' + imgs.pop().src + ')',
							  'display': 'block',
							  'width': '760px', 'height': '575px', 'top': '42px'});
			setTimeout(function () {
				$('#splash').addClass('unfold');
				if ($(window).height() <= $('#header').outerHeight(true) + 64 && 
					$(window).scrollTop() < ($('#header').outerHeight(true) + 64) - $(window).height()) setTimeout(function () {
					$('#splash').css({'top': '344px'})
					$('#intro').css({'z-index': 9999}).animate({'top': '-876px', 'margin-bottom': '-306px'}, 500, function() {
						$('#splash').addClass('down');
					});
				}, 1000);
			}, 100);
		});
		return;
	}
	splash_frames[i].css('left', '0');
	if (i && i != 16)
		splash_frames[i - 1].hide();
	setTimeout(function () {
		$splash_anim(i + 1, splash_frames);
	}, 1000 / 30);
};

var img, imgs = [], imgpaths = ['theme/splash.png', 'theme/splash_version.png'];

jQuery(function ($) {
	/* Infobox slider */
	$('<div id="info-link-box"><a href="#info">i</a></div>').prependTo('#infobox');
	$makeslider('#infobox', '#info', 'fixed-top');
	
	/* Donation box slider */
	if (location.protocol == 'file:') $makeslider('#donation-box', '#donate', 'fixed-center', 'fadeToggle');
	
	/* TOC toggles */
	$maketoggle('#toc li:has(ul) > a', 'ul', false);
	
	/* Download toggle */
	$maketoggle('#download h3', 'div');
	
	/* Linux downloads combo */
	$('#download div > div > a.button').mousedown(function () {
		$('#download div > div > ul.packages').slideToggle();
		return false;
	}).click(function () {
		return false;
	});
	
	/* Quickstart sub toggle */
	$maketoggle('#quickstart h3', 'div.toggle');
	
	/* Quickstart sub sub toggle */
	$maketoggle('#quickstart h4, #quickstart h5', 'ol, p');
	
	/* Requirements toggle */
	$maketoggle('#requirements-source h3', 'div');
	
	/* Driver install sub toggle */
	$maketoggle('#install-windows-driver h4, #install-windows-driver h5', 'ol, p');
	
	/* Install toggle */
	$maketoggle('#install h3', 'div');
	
	/* Hide issues list */
	$('#issues > ul').hide();
	
	/* Issues toggle */
	$maketoggle('#issues dt', '#issues dd');
	
	/* toggle on link click */
	$('a[href^="#"]:not([href^="#install-"])').click(function() {
		if (!$($(this).attr('href')).hasClass('expanded')) $($(this).attr('href')).click();
		return true;
	});
	
	/* Install toggle on link click */
	$('a[href^="#install-"]').click(function() {
		if (!$($(this).attr('href')).find('h3').hasClass('expanded')) $($(this).attr('href')).find('h3').click();
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
	$('#content p > br').after('<span class="indent"></span>')

	/* Intro */
	if ($(window).width() >= 760 &&
		(location.protocol != 'file:' ||
		 (location.search || '').indexOf('debug') > -1 ||
		 (document.cookie || '').indexOf('debug') > -1)) {
		$('#header').addClass('intro');
		function splash_onload() {
			this._loaded = true;
			for (var i = 0; i < imgs.length; i ++) if (!imgs[i]._loaded) return;
			var splash_wrapper = $('<div id="splash-wrapper"></div>'),
				splash = $('<div id="splash"><p id="splash_version_string"></p></div>'),
				splash_anim, splash_frames = [],
				splash_version_alpha = [0, .2, .4, .6, .8, 1, .95, .9, .85, .8, .75];
			splash.hide();
			splash.css('background-image', 'url(' + imgs[0].src + ')');
			/* Splash animation */
			for (var i = 2; i < imgs.length - 1; i ++) {
				splash_anim = $('<div id="splash_anim_' + splash_frames.length + '" class="splash_anim">');
				if (i > 2) splash_anim.css('left', '-9999px');
				splash_anim.css('background-image', 'url(' + imgs[i].src + ')');
				splash.append(splash_anim);
				splash_frames.push(splash_anim);
			}
			/* Major version animation */
			for (var i = 0; i < splash_version_alpha.length; i ++) {
				splash_anim = $('<div id="splash_anim_' + splash_frames.length + '" class="splash_anim">');
				splash_anim.css('left', '-9999px');
				splash_anim.css('background-image', 'url(' + imgs[1].src + ')');
				splash_anim.css('opacity', splash_version_alpha[i]);
				splash.append(splash_anim);
				splash_frames.push(splash_anim);
			}
			splash_wrapper.append(splash);
			$('#header').append(splash_wrapper);
			$('#splash_version_string').html($('#version').text());
			setTimeout(function () {
				$('#splash').fadeIn(566, function() {
					$splash_anim(0, splash_frames);
				});
			}, 500);
		}
		/* Get paths to remaining images */
		for (var i = 0; i < 16; i ++) {
			imgpaths.push('theme/splash_anim/splash_anim_' + (i < 9 ? '0' : '') + (i + 1) + '.png');
		}
		imgpaths.push('img/dispcalGUI-main_window-shadow-720.png');
		/* Load images */
		for (var i = 0; i < imgpaths.length; i ++) {
			img = new Image();
			imgs.push(img);
			img.onload = splash_onload;
			img.src = 'http://dispcalgui.hoech.net/' + imgpaths[i];
		}
	}
	
	/* Teaser */
	var interval = setInterval(function () {
		jQuery('#teaser img').fadeOut(750, function () {
			var src;
			if (jQuery('#teaser img').attr('src').indexOf('theme/dispcalGUI-adjust-reflection.png') > -1)
				src = 'theme/dispcalGUI-main_window-reflection.png';
			else
				src = 'theme/dispcalGUI-adjust-reflection.png';
			jQuery('#teaser img').attr('src', src).fadeIn(750);
		});
	}, 10000);
	
	/* Insert facebook page link into shariff bar */
	$('.shariff > ul').removeClass('col-5');
	$('.shariff > ul').addClass('col-6');
	$('.shariff > ul').prepend('<li class="shariff-button facebook info"><a title="Visit dispcalGUI on Facebook" target="_blank" href="https://www.facebook.com/dispcalGUI/"><span class="fa fa-facebook" style="width: 23px"></span></a></li>');

	/* Only show 'to top' link if scroll position > ToC offset top */
	var totop_isshown = false;
	$(window).scroll(function () {
		if (totop_isshown && $(window).scrollTop() < $('#toc').offset().top) {
			$('#totop').slideUp();
			totop_isshown = false;
		}
		else if (!totop_isshown && $(window).scrollTop() > $('#toc').offset().top) {
			$('#totop').slideDown();
			totop_isshown = true;
		}
	});
});

jQuery(window).load(function () {
	/* Anchor scroll effect */
	$.localScroll({hash: true, filter: ':not(a[href="#info"], #toc li:has(ul) > a)'});
	$.localScroll.hash();
	if (location.hash == '#donate') jQuery('a[href="#donate"]').click();
	
	/* Teaser */
	setTimeout(function () {
		var src = ['theme/dispcalGUI-main_window-reflection.png',
				   'theme/dispcalGUI-adjust-reflection.png'][Math.round(Math.random())];
		jQuery('#teaser img').attr('src', src).fadeIn(750);
	}, 500);
});
