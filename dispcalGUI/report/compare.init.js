if (jsapi.useragent.opera && jsapi.useragent.opera < 8) alert("Diese Seite funktioniert nicht mit Opera vor Version 8!");
else if (jsapi.useragent.msie && jsapi.useragent.mac) alert("Diese Seite funktioniert nicht mit Mac-Versionen des Internet Explorers! Verwenden Sie einen Mozilla-basierten Browser oder Safari in einer aktuellen Version.");
		
var data_ref, data_in,
	duplicates,
	fields_extract_indexes_i,
	fields_header = [];
		
window.onload = function() {
	memorize("in");
	memorize("ref");
	analyze()
};