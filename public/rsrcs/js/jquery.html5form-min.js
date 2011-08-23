(function($){$.fn.html5form=function(options){$(this).each(function(){var defaults={async:true,method:$(this).attr('method'),responseDiv:null,labels:'show',colorOn:'#000000',colorOff:'#a1a1a1',action:$(this).attr('action'),messages:false,emptyMessage:false,emailMessage:false,allBrowsers:false};var opts=$.extend({},defaults,options);if(!opts.allBrowsers){if($.browser.webkit&&parseInt($.browser.version)>=533){return false;}}
var form=$(this);var required=new Array();var email=new Array();function fillInput(input){if(input.attr('placeholder')){input.val(input.attr('placeholder'));input.css('color',opts.colorOff);if($.browser.mozilla){input.css('-moz-box-shadow','none');}}else{if(!input.data('value')){if(input.val()!=''){input.data('value',input.val());}}else{input.val(input.data('value'));}
input.css('color',opts.colorOn);}}
if(opts.labels=='hide'){$(this).find('label').hide();}
$.each($('select',this),function(){$(this).css('color',opts.colorOff);$(this).change(function(){$(this).css('color',opts.colorOn);});});$.each($(':input:not(:button, :submit, :radio, :checkbox, select)',form),function(i){fillInput($(this));if(this.getAttribute('required')!=null){required[i]=$(this);}
$('input').filter(this).each(function(){if(this.getAttribute('type')=='email'){email[i]=$(this);}});$(this).bind('focus',function(ev){ev.preventDefault();if(this.value==$(this).attr('placeholder')){if(this.getAttribute('type')!='url'){$(this).attr('value','');}}
$(this).css('color',opts.colorOn);});$(this).bind('blur',function(ev){ev.preventDefault();if(this.value==''){fillInput($(this));}
else{if((this.getAttribute('type')=='url')&&($(this).val()==$(this).attr('placeholder'))){fillInput($(this));}}});$('textarea').filter(this).each(function(){if($(this).attr('maxlength')>0){$(this).keypress(function(ev){var cc=ev.charCode||ev.keyCode;if(cc==37||cc==39){return true;}
if(cc==8||cc==46){return true;}
if(this.value.length>=$(this).attr('maxlength')){return false;}
else{return true;}});}});});{if(form.data('html5form')){return};form.data('html5form',true);form.bind('html5formvalidate',function(ev){var emptyInput=null;var emailError=null;var input=$(':input:not(:button, :submit, :radio, :checkbox, select)',form);required.length=0;$(input).each(function(i){if(this.getAttribute('required')!=null){required[i]=$(this);}});
$(required).each(function(key,value){if(value==undefined){return true;}
if(($(this).val()==$(this).attr('placeholder'))||($(this).val()=='')){emptyInput=$(this);if(opts.emptyMessage){$$.alerts.error(opts.emptyMessage);}
else if(opts.messages=='es'){$$.alerts.error('El campo '+$(this).attr('title')+' es requerido.');}
else if(opts.messages=='en'){$$.alerts.error('The '+$(this).attr('title')+' field is required.');}
else if(opts.messages=='it'){$$.alerts.error('Il campo '+$(this).attr('title')+' é richiesto.');}
else if(opts.messages=='de'){$$.alerts.error($(this).attr('title')+' ist ein Pflichtfeld.');}
else if(opts.messages=='fr'){$$.alerts.error('Le champ '+$(this).attr('title')+' est requis.');}
return false;}
return emptyInput;});$(email).each(function(key,value){if(value==undefined){return true;}
if($(this).val().search(/^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/i)){emailError=$(this);return false;}
return emailError;});if(!emptyInput&&!emailError){$(input).each(function(){if($(this).val()==$(this).attr('placeholder')){$(this).val('');}});if(opts.async){var formData=$(form).serialize();$.ajax({url:opts.action,type:opts.method,data:formData,success:function(data){if(opts.responseDiv){$$.alerts.error(data);}
$(input).val('');$.each(form[0],function(){fillInput($(this).not(':hidden, :button, :submit, :radio, :checkbox, select'));$('select',form).each(function(){$(this).css('color',opts.colorOff);$(this).children('option:eq(0)').attr('selected','selected');});$(':radio, :checkbox',form).removeAttr('checked');});}});}
else{return true;}}else{if(emptyInput){$(emptyInput).focus().select();}
else if(emailError){if(opts.emailMessage){$$.alerts.error(opts.emailMessage);}
else if(opts.messages=='es'){$$.alerts.error('Ingrese una dirección de correo válida por favor.');}
else if(opts.messages=='en'){$$.alerts.error('Please type a valid email address.');}
else if(opts.messages=='it'){$$.alerts.error("L'indirizzo e-mail non é valido.");}
else if(opts.messages=='de'){$$.alerts.error("Bitte eine gültige E-Mail-Adresse eintragen.");}
else if(opts.messages=='fr'){$$.alerts.error("Entrez une adresse email valide s’il vous plait.");}
$(emailError).select();}else{alert('Unknown Error');}}
ev.preventDefault(); return false;});}
});}})(jQuery);
